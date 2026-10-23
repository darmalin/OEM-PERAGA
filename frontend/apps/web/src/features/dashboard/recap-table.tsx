import type { Schemas } from "@ems/api";
import { Download } from "lucide-react";
import { Fragment, useState } from "react";

import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";

import { dayLabel, emptyRow, isWeekend, type Row, shortLabel, sumRows, TABLE_METRICS } from "./metrics";

type Key = Schemas["DashboardKey"];

export interface RecapTableProps {
  title: string;
  days: string[];
  rows: Row[];
  /** Absent: one row per day (Daily Comparison). Present: one row per key per day. */
  keys?: Key[];
  keyHeader?: string;
  /** Recap By User: Group (teams) and Exhibition Type columns. */
  userColumns?: boolean;
  fileName: string;
}

// Byte order mark so Excel opens the UTF-8 CSV with the right characters.
const BOM = String.fromCharCode(0xfeff);
const cell = (v: number) => (v ? formatNumber(v) : "");

/** Day by day, optionally by edition, source, or user, with a Total row per day. */
export function RecapTable({ title, days, rows, keys, keyHeader, userColumns, fileName }: RecapTableProps) {
  const [showEmpty, setShowEmpty] = useState(false);
  const at = new Map(rows.map((r) => [`${r.day}|${r.key ?? ""}`, r]));
  const get = (day: string, key: string | null) => at.get(`${day}|${key ?? ""}`) ?? emptyRow(day, key);
  const hasData = (r: Row) => TABLE_METRICS.some((m) => r[m] !== 0);

  const blocks = days.map((day) => {
    if (!keys) return { day, lines: [get(day, null)], total: null as Row | null };
    const lines = keys.map((k) => ({ ...get(day, k.id ?? null), key: k.id ?? null })).filter((r) => showEmpty || hasData(r));
    return { day, lines, total: sumRows(lines.length ? lines : [emptyRow(day)]) };
  });
  const keyOf = (id: string | null | undefined) => keys?.find((k) => (k.id ?? null) === (id ?? null));
  const grand = sumRows(keys ? blocks.map((b) => b.total!) : blocks.map((b) => b.lines[0]!));

  const download = () => {
    const head = ["Date", ...(keys ? [keyHeader ?? "Key"] : []), ...(userColumns ? ["Group", "Exhibition Type"] : []), ...TABLE_METRICS.map(shortLabel)];
    const lines = blocks.flatMap((b) => [
      ...b.lines.map((r) => [b.day, ...(keys ? [keyOf(r.key)?.label ?? ""] : []), ...(userColumns ? [keyOf(r.key)?.group ?? "", keyOf(r.key)?.editions ?? ""] : []), ...TABLE_METRICS.map((m) => r[m])]),
      ...(b.total ? [[b.day, "Total", ...(userColumns ? ["", ""] : []), ...TABLE_METRICS.map((m) => b.total![m])]] : []),
    ]);
    const csv = [head, ...lines].map((l) => l.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([BOM + csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileName}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const numCls = "px-3 py-2 text-right tabular";
  return (
    <section className="rounded-[12px] border border-line bg-bg" aria-label={title}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <h2 className="text-[14px] font-semibold">{title}</h2>
        <div className="flex items-center gap-3">
          {keys ? (
            <label className="flex items-center gap-2 text-[13px] text-muted">
              <Checkbox checked={showEmpty} onCheckedChange={(v) => setShowEmpty(v === true)} />
              Show empty rows
            </label>
          ) : null}
          <Button size="sm" onClick={download}><Download aria-hidden />Download CSV</Button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1100px] border-collapse text-[13px]">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr className="border-b border-line text-left text-[12px] text-label">
              <th scope="col" className="sticky left-0 bg-bg px-3 py-2 font-medium">Date</th>
              {keys ? <th scope="col" className="px-3 py-2 font-medium">{keyHeader}</th> : null}
              {userColumns ? <><th scope="col" className="px-3 py-2 font-medium">Group</th><th scope="col" className="px-3 py-2 font-medium">Exhibition Type</th></> : null}
              {TABLE_METRICS.map((m) => <th key={m} scope="col" className="px-3 py-2 text-right font-medium">{shortLabel(m)}</th>)}
            </tr>
          </thead>
          <tbody>
            {blocks.map((b) => {
              // Weekends are tinted like the old report (a hint only; the date says the day).
              const tint = isWeekend(b.day) ? "bg-[color-mix(in_srgb,var(--red-bg)_55%,transparent)]" : "";
              const span = b.lines.length + (b.total ? 1 : 0);
              return (
                <Fragment key={b.day}>
                  {b.lines.map((r, i) => (
                    <tr key={r.key ?? "none"} className={cn("border-b border-line", tint)}>
                      {i === 0 ? <th scope="rowgroup" rowSpan={span} className={cn("sticky left-0 bg-bg px-3 py-2 text-left align-top font-normal whitespace-nowrap", tint)}>{dayLabel(b.day)}</th> : null}
                      {keys ? <td className="px-3 py-2">{keyOf(r.key)?.label ?? "Unknown"}</td> : null}
                      {userColumns ? <><td className="px-3 py-2 text-muted">{keyOf(r.key)?.group ?? "-"}</td><td className="px-3 py-2 text-muted">{keyOf(r.key)?.editions ?? "-"}</td></> : null}
                      {TABLE_METRICS.map((m) => <td key={m} className={numCls}>{cell(r[m])}</td>)}
                    </tr>
                  ))}
                  {b.total ? (
                    <tr className={cn("border-b border-line font-medium", tint)}>
                      {b.lines.length === 0 ? <th scope="rowgroup" className={cn("sticky left-0 bg-bg px-3 py-2 text-left font-normal whitespace-nowrap", tint)}>{dayLabel(b.day)}</th> : null}
                      <td className="px-3 py-2" colSpan={userColumns ? 3 : 1}>Total</td>
                      {TABLE_METRICS.map((m) => <td key={m} className={numCls}>{cell(b.total![m])}</td>)}
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-line font-semibold">
              <th scope="row" className="sticky left-0 bg-bg px-3 py-2 text-left">Period</th>
              {keys ? <td className="px-3 py-2" colSpan={userColumns ? 3 : 1} /> : null}
              {TABLE_METRICS.map((m) => <td key={m} className={numCls}>{cell(grand[m])}</td>)}
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
