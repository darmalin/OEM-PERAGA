import { describe, expect, it } from "vitest";

import type { CacheMeta, CachedCredential, QueuedScan } from "./db";
import { backoffMs, Debouncer, provisionalResult } from "./decide";
import { localDate } from "./time";
import { uuid7 } from "./uuid7";

const HASH = "a".repeat(64);
const entry: CachedCredential = { token_hash: HASH, registration_code: "REG-0001", first_name: "Visitor", status: "ACTIVE" };
const meta: CacheMeta = {
  id: "meta",
  edition_id: "e",
  gate_id: "g",
  downloaded_at: "2027-03-10T01:00:00Z",
  expires_at: "2027-03-10T13:00:00Z",
  local_date: "2027-03-10",
  entered_today: [],
};
const now = new Date("2027-03-10T05:00:00Z");
const today = "2027-03-10";

function queued(patch: Partial<QueuedScan>): QueuedScan {
  return {
    scan_event_id: uuid7(),
    token_hash: HASH,
    scanned_at: "2027-03-10T04:00:00Z",
    local_date: today,
    provisional_result: null,
    sync_status: "synced",
    server_result: null,
    changed: false,
    ...patch,
  };
}

describe("provisionalResult", () => {
  const base = { entry, meta, now, today, earlierToday: [] as QueuedScan[] };

  it("first scan of the day is a first entry", () => {
    expect(provisionalResult(base)).toEqual({ result: "FIRST_ENTRY" });
  });

  it("repeat when the server said the visitor already entered today", () => {
    expect(provisionalResult({ ...base, meta: { ...meta, entered_today: [HASH] } })).toEqual({ result: "REPEAT_ENTRY" });
  });

  it("ignores entered_today of a cache built on an earlier day", () => {
    const old = { ...meta, local_date: "2027-03-09", entered_today: [HASH] };
    expect(provisionalResult({ ...base, meta: old })).toEqual({ result: "FIRST_ENTRY" });
  });

  it("repeat after an admitted scan in the local queue today", () => {
    const earlier = [queued({ server_result: "FIRST_ENTRY" })];
    expect(provisionalResult({ ...base, earlierToday: earlier })).toEqual({ result: "REPEAT_ENTRY" });
    const pending = [queued({ provisional_result: "FIRST_ENTRY", sync_status: "pending" })];
    expect(provisionalResult({ ...base, earlierToday: pending })).toEqual({ result: "REPEAT_ENTRY" });
  });

  it("an earlier rejected scan does not make a repeat", () => {
    const earlier = [queued({ server_result: "REJECTED_REVOKED", sync_status: "rejected" })];
    expect(provisionalResult({ ...base, earlierToday: earlier })).toEqual({ result: "FIRST_ENTRY" });
  });

  it("rejects unknown, revoked, and cancelled credentials", () => {
    expect(provisionalResult({ ...base, entry: undefined })).toEqual({ result: "REJECTED_UNKNOWN" });
    expect(provisionalResult({ ...base, entry: { ...entry, status: "REVOKED" } })).toEqual({ result: "REJECTED_REVOKED" });
    expect(provisionalResult({ ...base, entry: { ...entry, status: "CANCELLED" } })).toEqual({ result: "REJECTED_CANCELLED" });
  });

  it("does not decide without a cache or after it expired", () => {
    expect(provisionalResult({ ...base, meta: undefined })).toEqual({ reason: "NO_CACHE" });
    expect(provisionalResult({ ...base, now: new Date(meta.expires_at) })).toEqual({ reason: "CACHE_EXPIRED" });
  });
});

describe("localDate", () => {
  it("uses the edition timezone for the day boundary", () => {
    // 23:30 in Jakarta (UTC+7) is still the 10th; 00:30 is the 11th.
    expect(localDate(new Date("2027-03-10T16:30:00Z"), "Asia/Jakarta")).toBe("2027-03-10");
    expect(localDate(new Date("2027-03-10T17:30:00Z"), "Asia/Jakarta")).toBe("2027-03-11");
    expect(localDate(new Date("2027-03-10T17:30:00Z"), "UTC")).toBe("2027-03-10");
  });
});

describe("Debouncer", () => {
  it("ignores the same code within 3 s, while it keeps being read", () => {
    const d = new Debouncer(3000);
    expect(d.shouldIgnore("x", 0)).toBe(false);
    expect(d.shouldIgnore("x", 2000)).toBe(true);
    expect(d.shouldIgnore("x", 4500)).toBe(true);
    expect(d.shouldIgnore("y", 4600)).toBe(false);
    expect(d.shouldIgnore("x", 8000)).toBe(false);
  });
});

describe("backoffMs", () => {
  it("doubles from 5 s up to 5 min", () => {
    expect([1, 2, 3, 10].map(backoffMs)).toEqual([5000, 10000, 20000, 300000]);
  });
});

describe("uuid7", () => {
  it("is a version 7 UUID that sorts by time", () => {
    const a = uuid7(1_000);
    const b = uuid7(2_000);
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(a < b).toBe(true);
  });
});
