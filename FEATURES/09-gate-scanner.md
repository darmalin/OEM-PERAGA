# 09 Gate Scanner and Attendance

Spec §8. Open decisions D6, D9.

## Data
`gates` (per edition), `scanner_devices` (registered, bound to gate + edition, revocable, device secret hash), `scan_attempts` (every scan, valid or not, with `scan_event_id` unique), `visitor_checkins` (valid entries with `entry_type`).

## Rules
- First valid scan per registration per local event date (edition timezone): `FIRST_ENTRY`. Later the same day: `REPEAT_ENTRY`. Next day resets.
- No exit / check-out.
- Scanner only validates credentials of its own edition, enforced server-side.
- `scan_event_id` (UUID generated on device) is the idempotency key; retries never double count.

## Offline mode
- Device downloads an allowed-credential cache (token hashes + minimal display data, e.g. first name and registration ID) with an expiry.
- Scans queue locally in IndexedDB with status `pending`, `synced`, `rejected`.
- `POST /gate/scans/sync` accepts batches; server decides final First/Repeat by `scanned_at` order and returns per-item result.
- Offline result shown on device is provisional and labelled so.
- Device revoke invalidates the cache on next contact and blocks sync.

## Tasks
- [ ] Tables + unique `scan_event_id`.
- [ ] Device registration flow (supervisor generates a one-time activation code, device exchanges it for a device credential).
- [ ] `POST /gate/scans` (online), `POST /gate/scans/sync` (batch), `GET /gate/devices/{id}/cache`.
- [ ] Scanner PWA: activation, camera scan, result screen, offline queue, sync indicator, manual retry, cache expiry warning. See `DESIGN/DESIGN.md` "Scanner".
- [ ] Gate and device management screens (`gate.manage_devices`), scan history (`gate.view_history`), override (`gate.override`).
- [ ] Reconciliation report: scans changed from provisional result after sync.

## Acceptance criteria
- Same `scan_event_id` sent 5 times gives one `scan_attempts` row.
- Device of edition A scanning a QR of edition B gets `REJECTED_WRONG_EDITION`.
- Two offline devices scanning the same visitor the same day: after sync exactly one `FIRST_ENTRY`.
