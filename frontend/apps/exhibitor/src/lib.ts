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

export type ExhibitorRoute =
  | { page: "exhibitor"; id: string }
  | { page: "forms"; id: string }
  | { page: "form"; id: string; code: string }
  | { page: "review"; id: string; code: string };

/** "/e/{id}", "/e/{id}/forms", "/e/{id}/forms/{code}", "/e/{id}/forms/{code}/review". */
export function exhibitorRouteOf(route: string): ExhibitorRoute | null {
  const m = /^\/e\/([0-9a-f-]{36})(?:\/forms(?:\/([0-9]{2}[a-z]?)(\/review)?)?)?\/?$/.exec(route);
  if (!m?.[1]) return null;
  const [, id, code, review] = m;
  if (code) return review ? { page: "review", id, code } : { page: "form", id, code };
  return route.replace(/\/$/, "").endsWith("/forms") ? { page: "forms", id } : { page: "exhibitor", id };
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
  SUBMITTED: "Sent",
  RETURNED: "Returned",
  APPROVED: "Approved",
  CANCELLED: "Cancelled",
  NOT_STARTED: "Not Filled",
  IN_PROGRESS: "In Progress",
  NOT_REQUIRED: "Not Required",
  REGULAR: "Regular price",
  SURCHARGE: "Surcharge price",
  ONSITE: "Onsite price",
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
  SUBMITTED: "blue",
  APPROVED: "green",
  RETURNED: "amber",
  IN_PROGRESS: "amber",
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

/** Days from today to a calendar date: "In 5 days", "Today", "Tomorrow", "Past". */
export function timeLeft(value: string | null | undefined, now: Date = new Date()): string {
  if (!value) return "";
  const target = new Date(`${value}T00:00:00`);
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000);
  if (days < 0) return "Past";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  return `In ${days} days`;
}
