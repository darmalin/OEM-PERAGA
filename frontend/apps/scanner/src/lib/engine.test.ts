import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { db } from "./db";
import * as engine from "./engine";
import { sha256Hex } from "./hash";
import { getState, setState } from "./store";

/** A fake device API that keeps one row per scan_event_id, like the server. */
const server = {
  rows: new Map<string, string>(),
  revoked: false,
  down: false,
  syncCalls: 0,
};
const KNOWN = "token-known";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

async function fakeFetch(input: Request): Promise<Response> {
  if (server.down) throw new TypeError("Failed to fetch");
  const path = new URL(input.url).pathname;
  if (server.revoked && path !== "/api/v1/gate/device/activate")
    return json(403, { error: { code: "DEVICE_REVOKED", message: "This device was revoked. Ask a gate supervisor." } });
  const known = await sha256Hex(KNOWN);
  const decide = (hash: string) => (hash !== known ? "REJECTED_UNKNOWN" : [...server.rows.values()].includes("FIRST_ENTRY") ? "REPEAT_ENTRY" : "FIRST_ENTRY");
  if (path === "/api/v1/gate/device/scans/sync") {
    server.syncCalls += 1;
    const body = (await input.json()) as { items: { scan_event_id: string; token_hash: string; scanned_at: string }[] };
    const results = body.items.map((i) => {
      const result = server.rows.get(i.scan_event_id) ?? decide(i.token_hash);
      server.rows.set(i.scan_event_id, result);
      return { scan_event_id: i.scan_event_id, result, scanned_at: i.scanned_at, local_date: "2027-03-10", changed_from_provisional: false };
    });
    return json(200, { results });
  }
  return json(404, { error: { code: "NOT_FOUND", message: "Not found." } });
}

const context = {
  device_id: "00000000-0000-7000-8000-000000000001",
  device_name: "Phone 1",
  status: "ACTIVE" as const,
  edition_id: "e",
  edition_code: "IBTE2027",
  edition_timezone: "Asia/Jakarta",
  gate_id: "g",
  gate_code: "A",
  gate_name: "Gate A",
};

beforeEach(async () => {
  server.rows.clear();
  server.revoked = false;
  server.down = false;
  server.syncCalls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => fakeFetch(input as Request));
  vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
  await db.delete();
  await db.open();
  await db.device.put({ id: "device", token: `${context.device_id}.secret`, context, clock_offset_ms: 0 });
  await db.cache_meta.put({
    id: "meta",
    edition_id: "e",
    gate_id: "g",
    downloaded_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 3600_000 * 6).toISOString(),
    local_date: "2027-03-10",
    entered_today: [],
  });
  await db.credential_cache.put({ token_hash: await sha256Hex(KNOWN), registration_code: "REG-0001", first_name: "Visitor", status: "ACTIVE" });
  setState({ phase: "ready", device: context, link: "offline", error: null, goneMessage: null, syncing: false });
});

afterEach(() => {
  engine.stop();
  vi.restoreAllMocks();
});

describe("offline scan and sync", () => {
  it("queues a provisional result and stores only the token hash", async () => {
    const out = await engine.scan(KNOWN, "manual");
    expect(out).toMatchObject({ kind: "result", result: "FIRST_ENTRY", provisional: true, firstName: "Visitor" });
    const again = await engine.scan(KNOWN, "manual");
    expect(again).toMatchObject({ result: "REPEAT_ENTRY", provisional: true });
    const rows = await db.scan_queue.toArray();
    expect(rows).toHaveLength(2);
    expect(rows.every((r) => r.sync_status === "pending" && r.token_hash.length === 64)).toBe(true);
    expect(JSON.stringify(rows)).not.toContain(KNOWN);
  });

  it("ignores a camera double-read of the same code", async () => {
    expect(await engine.scan(KNOWN, "camera")).not.toBeNull();
    expect(await engine.scan(KNOWN, "camera")).toBeNull();
    expect(await db.scan_queue.count()).toBe(1);
  });

  it("syncs when online, and a batch sent twice does not duplicate", async () => {
    await engine.scan(KNOWN, "manual");
    await engine.scan("token-unknown", "manual");
    const batch = await db.scan_queue.toArray();

    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    await engine.syncNow();
    expect(await db.scan_queue.where("sync_status").equals("pending").count()).toBe(0);
    expect(getState().link).toBe("online");

    await engine.sendBatch(batch); // the same batch again, as after a lost response
    expect(server.rows.size).toBe(2);
    const synced = await db.scan_queue.toArray();
    expect(synced.map((s) => s.server_result).sort()).toEqual(["FIRST_ENTRY", "REJECTED_UNKNOWN"]);
    expect(synced.some((s) => s.changed)).toBe(false);
  });

  it("marks a scan whose server result differs from the provisional one", async () => {
    server.rows.set("other-device-scan", "FIRST_ENTRY"); // another gate admitted this visitor first
    await engine.scan(KNOWN, "manual");
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    await engine.syncNow();
    const [row] = await db.scan_queue.toArray();
    expect(row).toMatchObject({ provisional_result: "FIRST_ENTRY", server_result: "REPEAT_ENTRY", changed: true });
  });

  it("keeps pending scans and shows offline when the network fails", async () => {
    await engine.scan(KNOWN, "manual");
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    server.down = true;
    await engine.syncNow();
    expect(await db.scan_queue.where("sync_status").equals("pending").count()).toBe(1);
    expect(getState().link).toBe("offline");
  });

  it("wipes the device when the server says it was revoked", async () => {
    await engine.scan(KNOWN, "manual");
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(true);
    server.revoked = true;
    await engine.syncNow();
    expect(getState().phase).toBe("gone");
    expect(await db.scan_queue.count()).toBe(0);
    expect(await db.credential_cache.count()).toBe(0);
    expect(await db.device.count()).toBe(0);
  });
});
