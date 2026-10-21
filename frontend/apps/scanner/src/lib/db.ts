import type { Schemas } from "@ems/api";
import { Dexie, type EntityTable } from "dexie";

export type ScanResult = Schemas["ScanResult"];
export type DeviceContext = Schemas["DeviceContext"];

/** Offline cache row: only what the result screen shows (spec 8.3). */
export interface CachedCredential {
  token_hash: string;
  registration_code: string;
  first_name: string;
  /** ACTIVE, REVOKED, or CANCELLED (registration cancelled). */
  status: string;
}

export interface CacheMeta {
  id: "meta";
  edition_id: string;
  gate_id: string;
  downloaded_at: string;
  expires_at: string;
  /** Edition-local date the server built the cache on; entered_today is only valid that day. */
  local_date: string;
  /** Token hashes of registrations that already entered on local_date. */
  entered_today: string[];
}

export type SyncStatus = "pending" | "synced" | "rejected";

export interface QueuedScan {
  /** UUID v7 made at the moment of scan; never changes, including on retry. */
  scan_event_id: string;
  token_hash: string;
  /** Device time plus the server clock offset. */
  scanned_at: string;
  local_date: string;
  /** What the device showed while offline; null for online scans or when it could not decide. */
  provisional_result: ScanResult | null;
  sync_status: SyncStatus;
  server_result: ScanResult | null;
  /** Server result differs from the provisional one: for supervisor review. */
  changed: boolean;
}

export interface DeviceRecord {
  id: "device";
  /** X-Device-Token, "<device id>.<secret>". */
  token: string;
  context: DeviceContext;
  /** Server time minus device time, from the Date header of the last cache download. */
  clock_offset_ms: number;
}

export const db = new Dexie("ems-scanner") as Dexie & {
  device: EntityTable<DeviceRecord, "id">;
  credential_cache: EntityTable<CachedCredential, "token_hash">;
  cache_meta: EntityTable<CacheMeta, "id">;
  scan_queue: EntityTable<QueuedScan, "scan_event_id">;
};

db.version(1).stores({
  device: "id",
  credential_cache: "token_hash",
  cache_meta: "id",
  scan_queue: "scan_event_id, sync_status, scanned_at, [token_hash+local_date]",
});

/** Revoked or deactivated device: nothing of the event stays on the phone. */
export async function wipeAll(): Promise<void> {
  await db.transaction("rw", [db.device, db.credential_cache, db.cache_meta, db.scan_queue], async () => {
    await Promise.all([db.device.clear(), db.credential_cache.clear(), db.cache_meta.clear(), db.scan_queue.clear()]);
  });
}
