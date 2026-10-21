import { ApiError, call, type paths } from "@ems/api";
import createClient from "openapi-fetch";

/**
 * Device API client. The scanner authenticates with X-Device-Token, not a user session, so an
 * offline queue still syncs after the staff member's shift (backend checkin/router.py).
 */
export const deviceApi = createClient<paths>({
  baseUrl: location.origin,
  // Looked up per request, so tests can stub fetch after this module loads.
  fetch: (request) => globalThis.fetch(request),
});

let deviceToken: string | null = null;

export function setDeviceToken(token: string | null): void {
  deviceToken = token;
}

deviceApi.use({
  onRequest({ request }) {
    if (deviceToken) request.headers.set("X-Device-Token", deviceToken);
    return request;
  },
});

export { ApiError, call };

/** Requests give up after this long, so a dead network falls back to offline mode quickly. */
export const REQUEST_TIMEOUT_MS = 5000;

export function timeout(ms = REQUEST_TIMEOUT_MS): AbortSignal {
  return AbortSignal.timeout(ms);
}

/** True when the server answered (any status); false for network errors and timeouts. */
export function isServerAnswer(e: unknown): e is ApiError {
  return e instanceof ApiError && e.status < 500;
}

/** The device credential is gone for good: revoked, or unknown to the server. */
export function isDeviceGone(e: unknown): e is ApiError {
  return e instanceof ApiError && (e.code === "DEVICE_REVOKED" || e.code === "DEVICE_NOT_AUTHENTICATED");
}
