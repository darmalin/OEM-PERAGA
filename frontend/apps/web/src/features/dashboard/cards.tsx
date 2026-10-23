import { formatNumber } from "@/lib/format";

import { METRICS, type Row } from "./metrics";

const pct = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 1000) / 10}% of calls` : "");

/** The stat tiles: every number with its label, period, and share of calls. */
export function MetricCards({ row, period }: { row: Row; period: string }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-6">
      {METRICS.map((m) => (
        <div key={m.key} className="min-w-0 rounded-[10px] border border-line bg-bg px-4 py-3">
          <p className="truncate text-[12px] text-label">{m.label}</p>
          <p className="mt-0.5 text-[22px] leading-7 font-semibold tracking-[-0.01em] tabular">{formatNumber(row[m.key])}</p>
          <p className="truncate text-[12px] text-label">{m.calls ? pct(row[m.key], row.total) || period : period}</p>
        </div>
      ))}
    </div>
  );
}

/** Breakdown as a bar list: the bar is the share, the number is exact (no donut). */
export function Breakdown({ title, parts, row }: { title: string; parts: { key: keyof Row; label: string }[]; row: Row }) {
  const values = parts.map((p) => ({ ...p, value: Number(row[p.key]) }));
  const total = values.reduce((a, b) => a + b.value, 0);
  return (
    <section className="rounded-[12px] border border-line bg-bg p-5" aria-label={title}>
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="text-[14px] font-semibold">{title}</h2>
        <span className="text-[12px] text-label tabular">{formatNumber(total)} total</span>
      </div>
      <ul className="flex flex-col gap-3">
        {values.map((v) => (
          <li key={String(v.key)} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-1 text-[13px]">
            <span className="truncate">{v.label}</span>
            <span className="font-medium tabular">{formatNumber(v.value)}</span>
            <span className="w-12 text-right text-[12px] text-label tabular">{total ? `${Math.round((v.value / total) * 1000) / 10}%` : ""}</span>
            <span className="col-span-3 h-1.5 rounded-full bg-input" aria-hidden>
              <span className="block h-full rounded-full bg-primary" style={{ width: `${total ? (v.value / total) * 100 : 0}%` }} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
