import type { CacheMeta, CachedCredential, QueuedScan, ScanResult } from "./db";

export type NoDecision = "NO_CACHE" | "CACHE_EXPIRED";

const ADMITTED: ReadonlySet<ScanResult> = new Set(["FIRST_ENTRY", "REPEAT_ENTRY"]);

/** The result the server gave, or else the one the device showed. */
export function effectiveResult(scan: QueuedScan): ScanResult | null {
  return scan.server_result ?? scan.provisional_result;
}

/**
 * Offline result for one scan (scanner-pwa.md "Scan flow" step 3). Returns a reason instead of
 * a result when the cache is missing or expired: then the device must not guess.
 */
export function provisionalResult(input: {
  entry: CachedCredential | undefined;
  meta: CacheMeta | undefined;
  now: Date;
  today: string;
  /** Earlier scans of the same token hash on `today` (local queue). */
  earlierToday: readonly QueuedScan[];
}): { result: ScanResult } | { reason: NoDecision } {
  const { entry, meta, now, today, earlierToday } = input;
  if (!meta) return { reason: "NO_CACHE" };
  if (now.getTime() >= Date.parse(meta.expires_at)) return { reason: "CACHE_EXPIRED" };
  if (!entry) return { result: "REJECTED_UNKNOWN" };
  if (entry.status === "REVOKED") return { result: "REJECTED_REVOKED" };
  if (entry.status !== "ACTIVE") return { result: "REJECTED_CANCELLED" };
  const enteredOnServer = meta.local_date === today && meta.entered_today.includes(entry.token_hash);
  const enteredHere = earlierToday.some((s) => {
    const r = effectiveResult(s);
    return s.local_date === today && r !== null && ADMITTED.has(r);
  });
  return { result: enteredOnServer || enteredHere ? "REPEAT_ENTRY" : "FIRST_ENTRY" };
}

/**
 * Camera double-read guard: the same token is ignored while it keeps being read within
 * `windowMs` of the previous read (the QR stays in front of the camera after the result).
 */
export class Debouncer {
  private readonly seen = new Map<string, number>();

  constructor(private readonly windowMs = 3000) {}

  shouldIgnore(key: string, nowMs: number): boolean {
    const last = this.seen.get(key);
    this.seen.set(key, nowMs);
    for (const [k, t] of this.seen) if (nowMs - t > this.windowMs) this.seen.delete(k);
    return last !== undefined && nowMs - last <= this.windowMs;
  }
}

/** Retry delay after the n-th failed sync in a row: 5 s doubling, at most 5 min. */
export function backoffMs(failures: number): number {
  return Math.min(5000 * 2 ** Math.max(0, failures - 1), 300_000);
}
