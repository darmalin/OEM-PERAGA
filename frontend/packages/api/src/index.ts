import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type { components, paths };
export type Schemas = components["schemas"];

/** Error envelope returned by every failing API call (BACKEND_RULES/api.md). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: Record<string, string>;
  readonly requestId: string | null;

  constructor(status: number, body: unknown) {
    const err = (body as { error?: Partial<ApiErrorBody> } | null)?.error ?? {};
    super(err.message ?? `Request failed (${status}).`);
    this.status = status;
    this.code = err.code ?? "HTTP_ERROR";
    this.fields = err.fields ?? {};
    this.requestId = err.request_id ?? null;
  }
}

interface ApiErrorBody {
  code: string;
  message: string;
  fields: Record<string, string>;
  request_id: string | null;
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

const csrf: Middleware = {
  onRequest({ request }) {
    if (csrfToken && UNSAFE.has(request.method)) request.headers.set("X-CSRF-Token", csrfToken);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl: "", credentials: "include" });
api.use(csrf);

/** Unwrap an openapi-fetch result: data, or throw ApiError. */
export async function call<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw new ApiError(response.status, error);
  return data as T;
}

/** multipart/form-data requests (file uploads); same CSRF and error handling as `api`. */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const headers = new Headers();
  if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const res = await fetch(path, { method: "POST", body: form, headers, credentials: "include" });
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

/** Download a file the API streams (e.g. the import template) and save it. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await fetch(path, { credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => null));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
