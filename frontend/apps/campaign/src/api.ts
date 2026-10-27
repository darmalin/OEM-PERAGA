import type { Schemas } from "@ems/api";

export type Form = Schemas["PublicCampaignOut"];
export type Submission = Schemas["PublicSubmissionIn"];

export class FormError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly fields: Record<string, string>,
  ) {
    super(code);
  }
}

const base = (token: string) => `/api/v1/public/campaigns/${encodeURIComponent(token)}`;

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  // credentials "omit": the public form never sends the app's session cookie.
  const res = await fetch(url, { ...init, credentials: "omit", headers: { "Content-Type": "application/json" } });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = (body as { error?: { code?: string; fields?: Record<string, string> } } | null)?.error;
    throw new FormError(res.status, err?.code ?? "HTTP_ERROR", err?.fields ?? {});
  }
  return body as T;
}

export const loadForm = (token: string) => request<Form>(base(token));

export const submitForm = (token: string, body: Submission) =>
  request<{ status: string }>(`${base(token)}/registrations`, { method: "POST", body: JSON.stringify(body) });

/** /r/{token} -> token; anything else is not a campaign URL. */
export function tokenFromPath(pathname: string): string | null {
  const m = /^\/r\/([A-Za-z0-9_-]{1,64})\/?$/.exec(pathname);
  return m ? m[1]! : null;
}
