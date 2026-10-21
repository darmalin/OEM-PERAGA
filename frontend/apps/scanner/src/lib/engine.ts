import type { Schemas } from "@ems/api";

import { ApiError, call, deviceApi, isDeviceGone, isServerAnswer, setDeviceToken, timeout } from "./api";
import { type QueuedScan, type ScanResult, db, wipeAll } from "./db";
import { backoffMs, Debouncer, type NoDecision, provisionalResult } from "./decide";
import { sha256Hex } from "./hash";
import { getState, setState } from "./store";
import { localDate } from "./time";
import { uuid7 } from "./uuid7";

export const SYNC_BATCH = 100;
const CACHE_REFRESH_MS = 5 * 60_000;
const TICK_MS = 5000;
/** Synced scans older than this are dropped from the device; the server keeps the history. */
const KEEP_MS = 3 * 24 * 3600_000;

/** What the result screen shows for one scan. */
export type Outcome =
  | {
      kind: "result";
      result: ScanResult;
      provisional: boolean;
      firstName: string | null;
      registrationCode: string | null;
    }
  /** Offline with no usable cache: the scan is queued and the server decides later. */
  | { kind: "undecided"; reason: NoDecision }
  /** The server refused the scan for a reason that is not about the visitor (gate closed...). */
  | { kind: "error"; message: string };

let clockOffsetMs = 0;
let failures = 0;
let nextSyncAt = 0;
let lastCacheAt = 0;
let timer: ReturnType<typeof setInterval> | null = null;
const debouncer = new Debouncer();

function now(): Date {
  return new Date(Date.now() + clockOffsetMs);
}

function timezone(): string {
  return getState().device?.edition_timezone ?? "UTC";
}

// --- lifecycle -------------------------------------------------------------------------------

export async function start(): Promise<void> {
  const device = await db.device.get("device");
  if (!device) {
    setState({ phase: "activate" });
    return;
  }
  setDeviceToken(device.token);
  clockOffsetMs = device.clock_offset_ms;
  setState({ phase: "ready", device: device.context });
  await prune();
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  timer ??= setInterval(() => void tick(), TICK_MS);
  await refresh();
  await syncNow();
}

export function stop(): void {
  if (timer) clearInterval(timer);
  timer = null;
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
}

function onOnline(): void {
  failures = 0;
  nextSyncAt = 0;
  void refresh().then(syncNow);
}

function onOffline(): void {
  setState({ link: "offline" });
}

async function tick(): Promise<void> {
  if (getState().phase !== "ready" || !navigator.onLine) return;
  if (Date.now() - lastCacheAt >= CACHE_REFRESH_MS) await refresh();
  if (Date.now() >= nextSyncAt) await syncNow();
}

export async function activate(code: string): Promise<void> {
  const out = await call(
    deviceApi.POST("/api/v1/gate/device/activate", { body: { activation_code: code.trim() } }),
  );
  const { device_token, ...context } = out;
  await db.device.put({ id: "device", token: device_token, context, clock_offset_ms: 0 });
  await start();
}

/**
 * Revoked or unknown device: wipe the credential, cache, and queue (scanner-pwa.md). The server
 * already refused this device, so a final sync attempt would be refused the same way.
 */
async function deviceGone(e: ApiError): Promise<void> {
  stop();
  await wipeAll();
  setDeviceToken(null);
  setState({ phase: "gone", device: null, goneMessage: e.message, error: null, syncing: false });
}

export function startOver(): void {
  setState({ phase: "activate", goneMessage: null, link: navigator.onLine ? "online" : "offline" });
}

/** Network failures make the device offline; other failures are a visible sync error. */
async function failed(e: unknown): Promise<void> {
  if (isDeviceGone(e)) return deviceGone(e);
  if (e instanceof ApiError) setState({ link: "error", error: e.message });
  else setState({ link: "offline", error: null });
}

// --- cache -----------------------------------------------------------------------------------

/** Device context and the offline credential cache. Called on start, on a timer, and online. */
export async function refresh(): Promise<void> {
  if (getState().phase !== "ready") return;
  try {
    const me = await call(deviceApi.GET("/api/v1/gate/device/me", { signal: timeout() }));
    const sent = Date.now();
    // A large edition has tens of thousands of credentials; give the download time.
    const res = await deviceApi.GET("/api/v1/gate/device/cache", { signal: timeout(60_000) });
    if (!res.response.ok) throw new ApiError(res.response.status, res.error);
    const cache = res.data as Schemas["CacheOut"];
    clockOffsetMs = serverOffset(res.response.headers.get("date"), sent, Date.now(), clockOffsetMs);
    await saveCache(cache, me);
    lastCacheAt = Date.now();
    setState({ device: me, link: getState().link === "error" ? "error" : "online" });
  } catch (e) {
    await failed(e);
  }
}

/** Server minus device time from an HTTP Date header (1 s resolution, so small drift is kept). */
export function serverOffset(dateHeader: string | null, sentMs: number, receivedMs: number, current: number): number {
  const server = dateHeader ? Date.parse(dateHeader) : NaN;
  if (Number.isNaN(server)) return current;
  const offset = server + 500 - (sentMs + receivedMs) / 2;
  return Math.abs(offset - current) > 2000 ? Math.round(offset) : current;
}

async function saveCache(cache: Schemas["CacheOut"], me: Schemas["DeviceContext"]): Promise<void> {
  await db.transaction("rw", [db.credential_cache, db.cache_meta, db.device], async () => {
    await db.credential_cache.clear();
    await db.credential_cache.bulkPut(
      cache.credentials.map((c) => ({
        token_hash: c.token_hash,
        registration_code: c.registration_code,
        first_name: c.first_name,
        status: c.status,
      })),
    );
    await db.cache_meta.put({
      id: "meta",
      edition_id: cache.edition_id,
      gate_id: cache.gate_id,
      downloaded_at: new Date().toISOString(),
      expires_at: cache.expires_at,
      local_date: cache.local_date,
      entered_today: cache.entered_today,
    });
    await db.device.update("device", { context: me, clock_offset_ms: clockOffsetMs });
  });
}

async function prune(): Promise<void> {
  const cutoff = new Date(Date.now() - KEEP_MS).toISOString();
  await db.scan_queue
    .where("scanned_at")
    .below(cutoff)
    .filter((s) => s.sync_status !== "pending")
    .delete();
}

// --- scanning --------------------------------------------------------------------------------

/**
 * One scan from the camera or the manual field. Returns null for a camera double-read (the
 * same code within 3 s), which is ignored rather than sent twice.
 */
export async function scan(rawToken: string, source: "camera" | "manual"): Promise<Outcome | null> {
  const token = rawToken.trim();
  if (!token) return null;
  const tokenHash = await sha256Hex(token);
  if (source === "camera" && debouncer.shouldIgnore(tokenHash, Date.now())) return null;
  const scanEventId = uuid7();
  const scannedAt = now();
  if (navigator.onLine) {
    try {
      const out = await call(
        deviceApi.POST("/api/v1/gate/device/scans", {
          body: { scan_event_id: scanEventId, token_hash: tokenHash },
          signal: timeout(),
        }),
      );
      await db.scan_queue.put({
        scan_event_id: scanEventId,
        token_hash: tokenHash,
        scanned_at: out.scanned_at,
        local_date: out.local_date,
        provisional_result: null,
        sync_status: out.result.startsWith("REJECTED_") ? "rejected" : "synced",
        server_result: out.result,
        changed: false,
      });
      if (getState().link === "offline") setState({ link: "online" });
      return {
        kind: "result",
        result: out.result,
        provisional: false,
        firstName: out.first_name ?? null,
        registrationCode: out.registration_code ?? null,
      };
    } catch (e) {
      if (isDeviceGone(e)) {
        await deviceGone(e);
        return { kind: "error", message: e.message };
      }
      // The server refused for a reason unrelated to the visitor: do not guess offline.
      if (isServerAnswer(e)) return { kind: "error", message: e.message };
      setState({ link: "offline" });
    }
  }
  return scanOffline(scanEventId, tokenHash, scannedAt);
}

async function scanOffline(scanEventId: string, tokenHash: string, scannedAt: Date): Promise<Outcome> {
  const today = localDate(scannedAt, timezone());
  const [entry, meta, earlierToday] = await Promise.all([
    db.credential_cache.get(tokenHash),
    db.cache_meta.get("meta"),
    db.scan_queue.where("[token_hash+local_date]").equals([tokenHash, today]).toArray(),
  ]);
  const decision = provisionalResult({ entry, meta, now: scannedAt, today, earlierToday });
  const item: QueuedScan = {
    scan_event_id: scanEventId,
    token_hash: tokenHash,
    scanned_at: scannedAt.toISOString(),
    local_date: today,
    provisional_result: "result" in decision ? decision.result : null,
    sync_status: "pending",
    server_result: null,
    changed: false,
  };
  await db.scan_queue.put(item);
  if ("reason" in decision) return { kind: "undecided", reason: decision.reason };
  return {
    kind: "result",
    result: decision.result,
    provisional: true,
    firstName: entry?.first_name ?? null,
    registrationCode: entry?.registration_code ?? null,
  };
}

// --- sync ------------------------------------------------------------------------------------

let syncing: Promise<void> | null = null;

/** Send pending scans oldest first, in batches. Safe to call at any time; runs once at a time. */
export function syncNow(): Promise<void> {
  syncing ??= runSync().finally(() => {
    syncing = null;
  });
  return syncing;
}

/** The Retry button: sync right away, ignoring the backoff. */
export function retry(): Promise<void> {
  failures = 0;
  nextSyncAt = 0;
  return refresh().then(syncNow);
}

async function runSync(): Promise<void> {
  if (getState().phase !== "ready" || !navigator.onLine) return;
  setState({ syncing: true });
  try {
    for (;;) {
      const batch = await db.scan_queue.where("sync_status").equals("pending").sortBy("scanned_at");
      if (batch.length === 0) break;
      await sendBatch(batch.slice(0, SYNC_BATCH));
    }
    failures = 0;
    nextSyncAt = 0;
    setState({ link: "online", error: null });
  } catch (e) {
    failures += 1;
    nextSyncAt = Date.now() + backoffMs(failures);
    await failed(e);
  } finally {
    if (getState().phase === "ready") setState({ syncing: false });
  }
}

/** One batch. Sending the same batch twice is safe: scan_event_id is the idempotency key. */
export async function sendBatch(batch: readonly QueuedScan[]): Promise<void> {
  const out = await call(
    deviceApi.POST("/api/v1/gate/device/scans/sync", {
      body: {
        items: batch.map((s) => ({
          scan_event_id: s.scan_event_id,
          token_hash: s.token_hash,
          scanned_at: s.scanned_at,
          provisional_result: s.provisional_result,
        })),
      },
      signal: timeout(30_000),
    }),
  );
  await db.transaction("rw", db.scan_queue, async () => {
    for (const r of out.results) {
      const item = await db.scan_queue.get(r.scan_event_id);
      if (!item) continue;
      await db.scan_queue.put({
        ...item,
        local_date: r.local_date,
        sync_status: r.result.startsWith("REJECTED_") ? "rejected" : "synced",
        server_result: r.result,
        changed: item.provisional_result !== null && item.provisional_result !== r.result,
      });
    }
  });
}
