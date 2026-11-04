import { ApiError, type Schemas } from "@ems/api";
import { useEffect, useState } from "react";

export type Me = Schemas["PortalMeOut"];
export type ExhibitorRecord = Schemas["PortalExhibitorOut"];

/** Served at /exhibitor/ on the desk host, or at / on the portal's own host (EMS_PORTAL_BASE_URL). */
export function basePath(pathname: string): string {
  return pathname === "/exhibitor" || pathname.startsWith("/exhibitor/") ? "/exhibitor" : "";
}

const BASE = basePath(location.pathname);

/** The app route without the base: "/", "/login", "/accept-invite", "/e/{lead id}". */
export function routeOf(pathname: string): string {
  return pathname.slice(basePath(pathname).length) || "/";
}

export function href(to: string): string {
  return `${BASE}${to}`;
}

export function navigate(to: string, replace = false): void {
  if (replace) history.replaceState(null, "", href(to));
  else history.pushState(null, "", href(to));
  dispatchEvent(new PopStateEvent("popstate"));
}

/** The current route, following back/forward and navigate(). */
export function useRoute(): { route: string; search: URLSearchParams } {
  const [, setTick] = useState(0);
  useEffect(() => {
    const on = () => setTick((n) => n + 1);
    addEventListener("popstate", on);
    return () => removeEventListener("popstate", on);
  }, []);
  return { route: routeOf(location.pathname), search: new URLSearchParams(location.search) };
}

/** Lead id from "/e/{id}". */
export function exhibitorIdOf(route: string): string | null {
  return /^\/e\/([0-9a-f-]{36})\/?$/.exec(route)?.[1] ?? null;
}

const LABELS: Record<string, string> = {
  DRAFT: "Draft",
  SIGNED: "Signed",
  PENDING: "Pending",
  VERIFIED: "Verified",
  REJECTED: "Rejected",
  UNPAID: "Unpaid",
  PARTIAL: "Partially Paid",
  PAID: "Paid",
  BANK_TRANSFER: "Bank Transfer",
  CASH: "Cash",
  OTHER: "Other",
};

export function label(value: string | null | undefined): string {
  return value ? (LABELS[value] ?? value) : "";
}

const TONES: Record<string, string> = {
  SIGNED: "green",
  VERIFIED: "green",
  PAID: "green",
  PARTIAL: "amber",
  PENDING: "amber",
  REJECTED: "red",
};

export function toneOf(value: string): string {
  return TONES[value] ?? "gray";
}

/** "IDR 15,000,000" from the API's decimal strings. */
export function money(value: string | null | undefined, currency: string): string {
  if (value == null) return "";
  const amount = Number(value);
  const digits = Number.isInteger(amount) ? 0 : 2;
  return `${currency} ${new Intl.NumberFormat("en", { minimumFractionDigits: digits, maximumFractionDigits: 2 }).format(amount)}`;
}

/** dd-MM-yyyy, the format used across EMS. Dates (YYYY-MM-DD) are read as calendar days. */
export function date(value: string | null | undefined): string {
  if (!value) return "";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`;
}

/** Message for a failed call; field errors are shown under their fields instead. */
export function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "The server could not be reached. Check your connection and try again.";
}
