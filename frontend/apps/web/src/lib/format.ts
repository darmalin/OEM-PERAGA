import { TZDate } from "@date-fns/tz";
import { differenceInCalendarDays, format, formatDistanceToNowStrict } from "date-fns";

/** All API datetimes are UTC; the team reads them in the edition's timezone. */
export function formatDateTime(value: string | null | undefined, timezone?: string): string {
  if (!value) return "";
  const date = timezone ? new TZDate(value, timezone) : new Date(value);
  return format(date, "dd-MM-yyyy HH:mm:ss");
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  return format(new Date(value.length === 10 ? `${value}T00:00:00` : value), "dd-MM-yyyy");
}

export function relative(value: string | null | undefined): string {
  if (!value) return "";
  return formatDistanceToNowStrict(new Date(value), { addSuffix: true });
}

export function formatNumber(value: number | null | undefined): string {
  return value == null ? "" : new Intl.NumberFormat("en").format(value);
}

export function formatPercent(value: number | null | undefined): string {
  return value == null ? "n/a" : `${Math.round(value * 1000) / 10}%`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value == null) return "";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

/** "Opens in 140 days", "Day 2 of 3", "Ended 5 days ago", from event-local dates. */
export function eventCountdown(start: string, end: string, timezone: string): string {
  const today = new TZDate(Date.now(), timezone);
  const s = new Date(`${start}T00:00:00`);
  const e = new Date(`${end}T00:00:00`);
  const local = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const toStart = differenceInCalendarDays(s, local);
  const toEnd = differenceInCalendarDays(e, local);
  const length = differenceInCalendarDays(e, s) + 1;
  if (toStart > 1) return `Opens in ${toStart} days`;
  if (toStart === 1) return "Opens tomorrow";
  if (toEnd >= 0) return `Day ${length - toEnd} of ${length}`;
  return toEnd === -1 ? "Ended yesterday" : `Ended ${-toEnd} days ago`;
}

/** datetime-local input value (event-local) <-> ISO UTC. */
export function toLocalInput(iso: string | null | undefined, timezone: string): string {
  if (!iso) return "";
  return format(new TZDate(iso, timezone), "yyyy-MM-dd'T'HH:mm");
}

export function fromLocalInput(value: string, timezone: string): string | null {
  if (!value) return null;
  const [d, t] = value.split("T");
  const [y, m, day] = (d ?? "").split("-").map(Number);
  const [h, min] = (t ?? "00:00").split(":").map(Number);
  return new Date(new TZDate(y!, m! - 1, day!, h!, min!, timezone).getTime()).toISOString();
}
