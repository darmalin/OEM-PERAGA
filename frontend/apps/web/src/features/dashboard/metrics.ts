import type { Schemas } from "@ems/api";

export type Row = Schemas["DashboardRow"];
export type Metric = Exclude<keyof Row, "day" | "key">;

/**
 * Dashboard numbers in the old system's order. Call numbers count calls in the range: Answer /
 * Non Answer = first call answered / not; Recontacted / Retry No Answer = later calls (the old
 * "Follow-up Answered / No Answer"). Pending = leads never called by the end of the day.
 */
export const METRICS: { key: Metric; label: string; short?: string; calls?: boolean }[] = [
  { key: "added", label: "Added Leads", short: "Added" },
  { key: "pending", label: "Pending" },
  { key: "total", label: "Total Calls", short: "Total" },
  { key: "answer", label: "Answer", calls: true },
  { key: "non_answer", label: "Non Answer", calls: true },
  { key: "recontacted", label: "Recontacted", calls: true },
  { key: "retry_no_answer", label: "Retry No Answer", calls: true },
  { key: "valid", label: "Valid", calls: true },
  { key: "no_valid", label: "No Valid", calls: true },
  { key: "attend", label: "Attend", calls: true },
  { key: "attend_sourcing", label: "Attend Sourcing", calls: true },
  { key: "under_consideration", label: "Under Consideration", calls: true },
  { key: "not_attend", label: "Not Attend", calls: true },
  { key: "hang_up_immediately", label: "Hang Up Immediately", calls: true },
  { key: "b2b_matching", label: "B2B Matching", calls: true },
  { key: "b_side", label: "B-Side", calls: true },
  { key: "c_side", label: "C-Side", calls: true },
];

/** Table column order (Daily Comparison and the recaps), like the old system. */
export const TABLE_METRICS: Metric[] = [
  "added", "pending", "answer", "non_answer", "recontacted", "retry_no_answer", "total", "valid",
  "no_valid", "attend", "attend_sourcing", "under_consideration", "not_attend",
  "hang_up_immediately", "b2b_matching", "b_side", "c_side",
];

export const label = (m: Metric) => METRICS.find((x) => x.key === m)?.label ?? m;
export const shortLabel = (m: Metric) => {
  const def = METRICS.find((x) => x.key === m);
  return def?.short ?? def?.label ?? m;
};

export const emptyRow = (day: string | null = null, key: string | null = null): Row => ({
  day, key, added: 0, pending: 0, total: 0, answer: 0, non_answer: 0, recontacted: 0, retry_no_answer: 0,
  valid: 0, no_valid: 0, attend: 0, attend_sourcing: 0, under_consideration: 0, not_attend: 0,
  hang_up_immediately: 0, b2b_matching: 0, b_side: 0, c_side: 0,
});

/** Sum rows; Pending is a level, not a flow, so a total takes the last day's value. */
export function sumRows(rows: Row[]): Row {
  const out = emptyRow();
  for (const r of rows) for (const m of TABLE_METRICS) if (m !== "pending") out[m] += r[m];
  out.pending = rows.length ? rows[rows.length - 1]!.pending : 0;
  return out;
}

/** Every date from `from` to `to` (yyyy-MM-dd), inclusive. */
export function daysBetween(from: string, to: string): string[] {
  const out: string[] = [];
  const d = new Date(`${from}T00:00:00Z`);
  const end = new Date(`${to}T00:00:00Z`);
  while (d <= end) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return out;
}

export const isWeekend = (day: string) => [0, 6].includes(new Date(`${day}T00:00:00Z`).getUTCDay());

const DAY = new Intl.DateTimeFormat("en", { day: "numeric", month: "short", weekday: "short", timeZone: "UTC" });
/** "23 Sep (Wed)", like the old system. */
export function dayLabel(day: string): string {
  const parts = Object.fromEntries(DAY.formatToParts(new Date(`${day}T00:00:00Z`)).map((p) => [p.type, p.value]));
  return `${parts.day} ${parts.month} (${parts.weekday})`;
}
