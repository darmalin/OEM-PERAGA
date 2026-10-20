# Scanner PWA Rules

Spec §8, FEATURES/09, DESIGN.md "Scanner".

## App
- Separate Vite app `frontend/apps/scanner`, shares `@ems/ui` and `@ems/api`.
- `vite-plugin-pwa` with Workbox: precache the app shell; never cache API responses in the service worker (data lives in IndexedDB under app control).
- Served over HTTPS (camera and service worker need a secure context). In dev, use nginx with a local cert or `localhost`.
- Camera: `qr-scanner` (or `@zxing/browser`). Manual code entry as fallback.

## Device activation
- First run: enter the one-time activation code from a supervisor. Exchange for a device credential; store it in IndexedDB.
- The device is bound to one gate and one edition. Show both in the header at all times.
- If the server reports the device revoked: wipe the credential cache and queue (after attempting a final sync), show "This device was revoked. Ask a gate supervisor."

## Local data (Dexie / IndexedDB)

| Store | Content |
|---|---|
| `credential_cache` | Token hash, registration ID, first name, status. Nothing else. |
| `cache_meta` | Edition, gate, downloaded_at, expires_at |
| `scan_queue` | `scan_event_id` (UUID v7), token hash, scanned_at (device time + offset), provisional result, sync status (`pending`, `synced`, `rejected`), server result |

- Hash the scanned token on device (SHA-256 via Web Crypto) and look up in `credential_cache`. Raw tokens are not stored.
- Cache refresh when online on a timer and on app start; block offline validation once `expires_at` passes and show why.

## Scan flow
1. Generate `scan_event_id` at the moment of scan. It never changes, including on retry.
2. Online: `POST /gate/scans`; show the server result.
3. Offline or request failed: decide provisional FIRST/REPEAT from the local queue for today (edition timezone), show it with "Provisional", add to `scan_queue` as `pending`.
4. Debounce: the same token within 3 seconds is ignored on the device (camera double-read), not sent twice.

## Sync
- Background sync when online: send pending items in batches (e.g. 100) to `POST /gate/scans/sync`. Retry with backoff. The server result overwrites the provisional one.
- Items whose server result differs from the provisional one are marked so the supervisor can review.
- Header shows Online / Offline (n pending) / Sync error + Retry. Pending count never disappears until the server confirms.

## UI
- Full-screen result (2 s, tap to dismiss), word + icon + color + vibration pattern per result (DESIGN.md).
- Controls ≥ 56px, text ≥ 18px, works one-handed in portrait.
- English only.

## Tests
- Unit: provisional decision, debounce, timezone day boundary.
- Integration (Playwright, offline emulation): scan offline, go online, verify synced and no duplicates when the same batch is sent twice.
