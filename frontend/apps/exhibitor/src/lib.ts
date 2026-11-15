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
  | { page: "contract"; id: string }
  | { page: "forms"; id: string }
  | { page: "form"; id: string; code: string }
  | { page: "review"; id: string; code: string };

/** "/e/{id}", "/e/{id}/contract", "/e/{id}/forms", "/e/{id}/forms/{code}", "/e/{id}/forms/{code}/review". */
export function exhibitorRouteOf(route: string): ExhibitorRoute | null {
  const m = /^\/e\/([0-9a-f-]{36})(?:\/(contract)|\/forms(?:\/([0-9]{2}[a-z]?)(\/review)?)?)?\/?$/.exec(route);
  if (!m?.[1]) return null;
  const [, id, contract, code, review] = m;
  if (contract) return { page: "contract", id };
  if (code) return review ? { page: "review", id, code } : { page: "form", id, code };
  return route.replace(/\/$/, "").endsWith("/forms") ? { page: "forms", id } : { page: "exhibitor", id };
}

export type Theme = "peraga" | "inatex" | "indo-intertex";

export interface Brand {
  theme: Theme;
  /** The show's logo in the header; PERAGA Expo's when the show has none. */
  logo: { src: string; alt: string; width: number; height: number };
  /** Wide banner on the exhibition home, when the show has one. */
  banner: string | null;
}

const ASSET = `${import.meta.env.BASE_URL}brand/`;
const PERAGA_LOGO = { src: `${import.meta.env.BASE_URL}peraga-expo-logo.png`, alt: "PERAGA Expo", width: 165, height: 29 };

/**
 * Each show keeps its own colour and logo, as in the old exhibitor manual: INATEX red, Indo Intertex
 * green. Matched on the exhibition's code or name, so a new edition of the same show needs no setup.
 */
export function brandOf(record: Pick<ExhibitorRecord, "exhibition_code" | "exhibition_name"> | null | undefined): Brand {
  const key = `${record?.exhibition_code ?? ""} ${record?.exhibition_name ?? ""}`.toLowerCase();
  if (/inatex/.test(key)) {
    return { theme: "inatex", logo: { src: `${ASSET}inatex-logo.png`, alt: "INATEX", width: 122, height: 32 }, banner: `${ASSET}inatex-banner.jpg` };
  }
  if (/intertex|\biit\b/.test(key)) {
    return { theme: "indo-intertex", logo: { src: `${ASSET}indo-intertex-logo.png`, alt: "Indo Intertex", width: 125, height: 32 }, banner: null };
  }
  return { theme: "peraga", logo: PERAGA_LOGO, banner: null };
}

/** Counts of the order forms by where the exhibitor stands, for the home card and the list. */
export function formCounts(forms: { progress: string }[]): { notFilled: number; inProgress: number; sent: number; done: number } {
  const count = (...values: string[]) => forms.filter((f) => values.includes(f.progress)).length;
  return {
    notFilled: count("NOT_STARTED"),
    inProgress: count("IN_PROGRESS"),
    sent: count("SUBMITTED", "APPROVED"),
    done: count("SUBMITTED", "APPROVED", "NOT_REQUIRED"),
  };
}

/** "15 APR" style parts of a calendar date, for the date tiles. */
export function dayParts(value: string): { day: string; month: string } {
  const d = new Date(`${value}T00:00:00`);
  return { day: String(d.getDate()), month: d.toLocaleString("en", { month: "short" }).toUpperCase() };
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

/** "23 September 2026", as the old manual writes deadlines. Calendar days. */
export function longDate(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" });
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

/** Where the show stands from today: "Starts in 40 days", "On now", "Ended". Calendar days. */
export function showCountdown(start: string, end: string, now: Date = new Date()): { text: string; live: boolean } {
  const day = (v: string) => new Date(`${v}T00:00:00`).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const toStart = Math.round((day(start) - today) / 86_400_000);
  if (toStart > 1) return { text: `Starts in ${toStart} days`, live: false };
  if (toStart === 1) return { text: "Starts tomorrow", live: false };
  if (today <= day(end)) return { text: "On now", live: true };
  return { text: "Ended", live: false };
}

/** Whole days from today to a calendar date (negative once past); null without a date. */
export function daysUntil(value: string | null | undefined, now: Date = new Date()): number | null {
  if (!value) return null;
  const target = new Date(`${value}T00:00:00`).getTime();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((target - today) / 86_400_000);
}
