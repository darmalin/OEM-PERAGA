import type { Schemas } from "@ems/api";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { Fragment, useState } from "react";

import { formatNumber } from "@/lib/format";
import { Button } from "@/ui/button";

import { ReportTableHead } from "./report-table-head";

import { dayLabel, daysBetween, emptyRow, type Row } from "./metrics";

export const DETAIL_GROUPS = [
  { label: "Lead Acquisition", tone: "acquisition", columns: [
    { label: "Added", value: (r: Row) => r.added }, { label: "Pending", value: (r: Row) => r.pending },
    { label: "Answer", value: (r: Row) => r.answer + r.recontacted }, { label: "No Answer", value: (r: Row) => r.non_answer + r.retry_no_answer }, { label: "Total", value: (r: Row) => r.total },
  ] },
  { label: "Lead Validity", tone: "validity", columns: [{ label: "Valid", value: (r: Row) => r.valid }, { label: "Invalid", value: (r: Row) => r.no_valid }] },
  { label: "Attendance", tone: "attendance", columns: [
    { label: "Attend", value: (r: Row) => r.attend + r.attend_sourcing }, { label: "Under Consideration", value: (r: Row) => r.under_consideration },
    { label: "Not Attend", value: (r: Row) => r.not_attend }, { label: "Hang Up", value: (r: Row) => r.hang_up_immediately },
  ] },
  { label: "Buyer Type", tone: "buyer", columns: [{ label: "B2B Matching", value: (r: Row) => r.b2b_matching }, { label: "B-Side", value: (r: Row) => r.b_side }, { label: "C-Side", value: (r: Row) => r.c_side }] },
];
const columns = DETAIL_GROUPS.flatMap(g => g.columns);
const displayed = (value: number) => value ? formatNumber(value) : "–";
const hasData = (row: Row) => columns.some(c => c.value(row) !== 0);
export function SourceDetail({ from, to, total, daily, rows, sources, breakdownLabel = "Source", description }: {
  from: string; to: string; total: Row; daily: Row[]; rows: Row[]; sources: Schemas["DashboardKey"][]; breakdownLabel?: string; description?: string;
}) {
  const days = daysBetween(from, to);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(days.slice(0, 1)));
  const dailyMap = new Map(daily.map(r => [r.day, r]));
  const sourceLabels = new Map(sources.map(s => [s.id, s.label]));
  const byDay = new Map<string, Row[]>();
  for (const row of rows) if (row.day && hasData(row)) byDay.set(row.day, [...(byDay.get(row.day) ?? []), row]);
  const toggle = (day: string) => setExpanded(prev => { const next = new Set(prev); if (next.has(day)) next.delete(day); else next.add(day); return next; });
  const name = (row: Row) => sourceLabels.get(row.key ?? null) ?? `Unspecified ${breakdownLabel.toLowerCase()}`;
  const download = () => {
    const records: (string | number)[][] = [[`Date / ${breakdownLabel}`, ...columns.map(c => c.label)]];
    for (const day of days) {
      const row = dailyMap.get(day) ?? emptyRow(day);
      records.push([day, ...columns.map(c => c.value(row))]);
      for (const source of byDay.get(day) ?? []) records.push([`${day} / ${name(source)}`, ...columns.map(c => c.value(source))]);
    }
    records.push(["Grand Total", ...columns.map(c => c.value(total))]);
    const csv = records.map(line => line.map(v => `"${String(v).replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `lead-detail-${from}-${to}.csv`; anchor.click(); URL.revokeObjectURL(url);
  };
  return <section className="dash-card min-w-0 overflow-hidden" aria-label={`Detail by Date & ${breakdownLabel}`}>
    <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4"><div><h2 className="text-[15px] font-bold">Detail by Date &amp; {breakdownLabel}</h2>{description ? <p className="mt-1 text-[12px] text-label">{description}</p> : null}</div><Button className="border border-line bg-bg hover:bg-subtle" onClick={download}><Download aria-hidden />Export CSV</Button></div>
    <div className="max-h-[540px] overflow-auto">
      <table className="dash-detail-table w-full min-w-[1230px] border-collapse text-[12px]">
        <caption className="sr-only">Daily lead and call metrics, expandable by {breakdownLabel.toLowerCase()}. Pending is the end-of-day balance. Grand Total uses period totals.</caption>
        <ReportTableHead identities={[`Date / ${breakdownLabel}`]} groups={DETAIL_GROUPS} />
        <tbody>{days.map(day => {
          const row = dailyMap.get(day) ?? emptyRow(day), details = byDay.get(day) ?? [], open = expanded.has(day);
          return <Fragment key={day}>
            <tr className="dash-date-row border-y border-line font-semibold">
              <th scope="row" className="dash-date-row sticky left-0 z-[1] px-3 text-left"><button type="button" className="flex min-h-10 w-full items-center gap-2 rounded px-1 text-left focus-visible:outline-focus" aria-expanded={open} aria-label={`${open ? "Collapse" : "Expand"} ${dayLabel(day)}`} onClick={() => toggle(day)}>{open ? <ChevronDown className="size-4 shrink-0" aria-hidden /> : <ChevronRight className="size-4 shrink-0" aria-hidden />}<span className="whitespace-nowrap">{dayLabel(day).replace(" (", ` ${day.slice(0, 4)} (`)}</span></button></th>
              {columns.map(c => <td key={c.label} className="border-x border-line px-2 py-2 text-center tabular">{displayed(c.value(row))}</td>)}
            </tr>
            {open ? details.length ? details.map(source => <tr key={source.key ?? "none"} className="border-b border-line hover:bg-subtle"><th scope="row" className="sticky left-0 bg-bg py-2 pr-3 pl-10 text-left font-normal">{name(source)}</th>{columns.map(c => <td key={c.label} className="border-x border-line px-2 py-2 text-center text-muted tabular">{displayed(c.value(source))}</td>)}</tr>) : <tr className="border-b border-line"><td colSpan={columns.length + 1} className="px-10 py-3 text-[12px] text-label">No detail is recorded for this date and the selected filters.</td></tr> : null}
          </Fragment>;
        })}</tbody>
        <tfoot className="sticky bottom-0 z-[2]"><tr className="dash-grand-total border-t border-line font-bold"><th scope="row" className="dash-grand-total sticky left-0 px-4 py-4 text-left">Grand Total</th>{columns.map(c => <td key={c.label} className="border-x border-line px-2 py-4 text-center tabular">{displayed(c.value(total))}</td>)}</tr></tfoot>
      </table>
    </div>
  </section>;
}
