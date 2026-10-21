import { TZDate } from "@date-fns/tz";
import { format } from "date-fns";

/** Event-local date (yyyy-MM-dd) of an instant: first entry resets each local day (spec 8.2). */
export function localDate(instant: Date, timezone: string): string {
  return format(new TZDate(instant, timezone), "yyyy-MM-dd");
}

/** Time of day in the edition timezone, for the recent scans list. */
export function localTime(iso: string, timezone: string): string {
  return format(new TZDate(new Date(iso), timezone), "HH:mm:ss");
}
