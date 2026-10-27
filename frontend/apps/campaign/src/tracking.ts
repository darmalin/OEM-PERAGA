/**
 * Google Tag Manager and UTM tags for a campaign form.
 * dataLayer events carry no personal data: never names, emails, or phone numbers.
 */
const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"] as const;
export type Utm = Partial<Record<(typeof UTM_KEYS)[number], string>>;

export function readUtm(search: string): Utm {
  const params = new URLSearchParams(search);
  const out: Utm = {};
  for (const key of UTM_KEYS) {
    const value = params.get(key)?.trim();
    if (value) out[key] = value.slice(0, 200);
  }
  return out;
}

declare global {
  interface Window {
    dataLayer?: Record<string, unknown>[];
  }
}

const GTM_RE = /^GTM-[A-Z0-9]{4,12}$/;

/** Load the container once. The ID comes from the server and is checked again here. */
export function loadGtm(id: string | null | undefined): void {
  if (!id || !GTM_RE.test(id) || document.getElementById("gtm-loader")) return;
  window.dataLayer = window.dataLayer ?? [];
  window.dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
  const s = document.createElement("script");
  s.id = "gtm-loader";
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(id)}`;
  document.head.appendChild(s);
}

export type FormEvent = "campaign_form_view" | "campaign_form_start" | "campaign_form_submit";

export function track(event: FormEvent, data: { edition: string; language: string }): void {
  window.dataLayer = window.dataLayer ?? [];
  window.dataLayer.push({ event, form_edition: data.edition, form_language: data.language });
}
