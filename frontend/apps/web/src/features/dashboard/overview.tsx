import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Check, Clock3, Phone, UserPlus, X } from "lucide-react";

import { formatNumber } from "@/lib/format";
import { ErrorState, Skeleton } from "@/ui/states";

import { dashboardQuery, type DashboardSearch } from "./api";
import { emptyRow, type Row } from "./metrics";
import { SourceDetail } from "./source-detail";

export const answeredCalls = (row: Row) => row.answer + row.recontacted;
export const unansweredCalls = (row: Row) => row.non_answer + row.retry_no_answer;
export function previousPeriod(from: string, to: string) {
  const start = new Date(`${from}T00:00:00Z`).getTime();
  const end = new Date(`${to}T00:00:00Z`).getTime();
  return { from: new Date(start - (end - start + 864e5)).toISOString().slice(0, 10), to: new Date(start - 864e5).toISOString().slice(0, 10) };
}
export function changeLabel(value: number, before: number) {
  if (!before) return value ? "New in period" : "No change";
  return `${Math.abs(Math.round((value - before) / before * 1000) / 10)}%`;
}
const colors = { blue: "#1688f5", yellow: "#ffc32a", green: "#19a667", red: "#f36770", purple: "#9156e8", cyan: "#55b9ef", amber: "#f5ad16", teal: "#13bba7", navy: "#2356b7", gray: "#c8cfd5" };
const tiles = [
  { label: "Total Added", value: (r: Row) => r.added, icon: UserPlus, tone: "blue", negative: false, hint: "Leads added in this period" },
  { label: "Pending", value: (r: Row) => r.pending, icon: Clock3, tone: "amber", negative: true, hint: "Leads not yet called at period end" },
  { label: "Answer", value: answeredCalls, icon: Phone, tone: "blue", negative: false, hint: "All answered calls, including recontacts" },
  { label: "No Answer", value: unansweredCalls, icon: X, tone: "red", negative: true, hint: "All unanswered calls, including retries" },
  { label: "Valid Lead", value: (r: Row) => r.valid, icon: Check, tone: "green", negative: false, hint: "Calls recorded with Valid Lead verification" },
  { label: "Invalid", value: (r: Row) => r.no_valid, icon: X, tone: "red", negative: true, hint: "Calls recorded with Invalid verification" },
] as const;

type Slice = { label: string; value: number; color: string };
const percent = (n: number, total: number) => `${total ? (n / total * 100).toFixed(1) : "0.0"}%`;
function Donut({ values, caption }: { values: Slice[]; caption: string }) {
  const total = values.reduce((sum, s) => sum + s.value, 0);
  return (
    <svg viewBox="0 0 220 220" className="aspect-square w-full max-w-[225px] shrink-0" role="img" aria-label={`${caption}: ${formatNumber(total)}. ${values.map(s => `${s.label} ${formatNumber(s.value)}`).join(", ")}`}>
      <circle cx="110" cy="110" r="82" fill="none" stroke="var(--surface-input)" strokeWidth="32" />
      {values.map((s, index) => {
        const length = total ? s.value / total * 100 : 0;
        const start = total ? values.slice(0, index).reduce((sum, value) => sum + value.value, 0) / total * 100 : 0;
        return <circle key={s.label} cx="110" cy="110" r="82" fill="none" stroke={s.color} strokeWidth="32" pathLength="100" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-start} transform="rotate(-90 110 110)"><title>{s.label}: {formatNumber(s.value)} ({percent(s.value, total)})</title></circle>;
      })}
      <text x="110" y="108" textAnchor="middle" fill="var(--ink)" fontSize="23" fontWeight="700">{formatNumber(total)}</text>
      <text x="110" y="129" textAnchor="middle" fill="var(--ink-label)" fontSize="12">{caption}</text>
    </svg>
  );
}
function Legend({ values }: { values: Slice[] }) {
  const total = values.reduce((sum, s) => sum + s.value, 0);
  return <ul className="flex min-w-0 flex-1 flex-col gap-4">{values.map(s => <li key={s.label} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2 text-[12px]">
    <span className="flex min-w-0 items-center gap-2"><span className="size-2.5 shrink-0 rounded-full" style={{ background: s.color }} /><span>{s.label}</span></span>
    <span className="font-semibold tabular">{formatNumber(s.value)}</span><span className="text-label tabular">{percent(s.value, total)}</span>
  </li>)}</ul>;
}
function StatusBars({ row }: { row: Row }) {
  const bars = [
    { label: "Valid", value: row.valid, color: colors.green }, { label: "Invalid", value: row.no_valid, color: colors.red },
    { label: "Attend", value: row.attend + row.attend_sourcing, color: colors.blue }, { label: "Under Consideration", value: row.under_consideration, color: colors.purple },
    { label: "Not Attend", value: row.not_attend, color: colors.amber }, { label: "Hang Up", value: row.hang_up_immediately, color: colors.teal },
  ];
  const maximum = Math.max(1, ...bars.map(b => b.value));
  const raw = maximum / 4, magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(1, ([1, 2, 5, 10].find(n => n * magnitude >= raw) ?? 10) * magnitude);
  const ceiling = step * 4;
  return <svg viewBox="0 0 540 235" role="img" aria-label={`Lead Status Breakdown. ${bars.map(b => `${b.label}: ${b.value}`).join(", ")}`} className="mt-3 w-full">
    {[0, 1, 2, 3, 4].map(i => <g key={i}><line x1="42" y1={176 - i * 36} x2="532" y2={176 - i * 36} stroke="var(--border)" /><text x="35" y={180 - i * 36} textAnchor="end" fill="var(--ink-label)" fontSize="10">{formatNumber(step * i)}</text></g>)}
    {bars.map((b, i) => {
      const x = 58 + i * 80, h = b.value / ceiling * 144;
      const words = b.label.split(" ");
      return <g key={b.label}><title>{b.label}: {formatNumber(b.value)}</title><rect x={x} y={176 - h} width="48" height={h} rx="2" fill={b.color} /><text x={x + 24} y={Math.max(15, 169 - h)} textAnchor="middle" fill="var(--ink)" fontSize="11" fontWeight="600">{formatNumber(b.value)}</text>
        <text x={x + 24} y="195" textAnchor="middle" fill="var(--ink-label)" fontSize="10">{words.map((w, j) => <tspan key={w} x={x + 24} dy={j ? 12 : 0}>{w}</tspan>)}</text></g>;
    })}
  </svg>;
}

export function ReferenceOverview({ s }: { s: DashboardSearch }) {
  const total = useQuery(dashboardQuery(s, "total"));
  const previous = useQuery(dashboardQuery(s, "total", previousPeriod(s.from, s.to)));
  const daily = useQuery(dashboardQuery(s, "day"));
  const sources = useQuery(dashboardQuery(s, "day_source"));
  if (total.isPending) return <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">{tiles.map(t => <Skeleton key={t.label} className="h-[124px]" />)}</div>;
  if (total.isError) return <ErrorState error={total.error} onRetry={() => void total.refetch()} />;
  const row = total.data.rows[0] ?? emptyRow();
  const before = previous.data?.rows[0] ?? emptyRow();
  const responses = [{ label: "Answer", value: answeredCalls(row), color: colors.blue }, { label: "No Answer", value: unansweredCalls(row), color: colors.yellow }];
  const buyers = [{ label: "B-Side", value: row.b_side, color: colors.navy }, { label: "C-Side", value: row.c_side, color: colors.cyan }, { label: "Others", value: Math.max(0, row.total - row.b_side - row.c_side), color: colors.gray }];
  return <div className="dashboard-reference flex flex-col gap-4">
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {tiles.map(t => {
        const value = t.value(row), old = t.value(before), up = value > old;
        const good = value === old || (up !== t.negative);
        const Arrow = up ? ArrowUp : ArrowDown;
        return <section key={t.label} className="dash-card relative min-w-0 px-5 py-4" aria-label={t.label} title={t.hint}>
          <span className={`dash-icon dash-icon-${t.tone}`}><t.icon className="size-5" strokeWidth={1.8} aria-hidden /></span>
          <p className="pr-10 text-[12px] text-muted">{t.label}</p><p className="mt-1 text-[27px] leading-8 font-bold tracking-tight tabular">{formatNumber(value)}</p>
          <p className={`mt-3 flex items-center gap-1 text-[12px] font-semibold ${good ? "dash-positive" : "dash-negative"}`} title="Compared with the previous period of the same length">
            {previous.isPending ? <span className="text-label">Loading comparison…</span> : previous.isError ? <span className="text-label">Comparison unavailable</span> : <>{value !== old && old > 0 ? <Arrow className="size-3.5" aria-hidden /> : null}{changeLabel(value, old)}</>}
          </p>
        </section>;
      })}
    </div>
    {!row.total && !row.added && !row.pending ? <p role="status" className="rounded-[8px] border border-line bg-bg px-4 py-3 text-[13px] text-label">No activity was recorded for the selected period and filters.</p> : null}
    <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[1.05fr_1.3fr_0.95fr]">
      <section className="dash-card min-w-0 p-5" aria-label="Lead Response Overview">
        <div className="flex items-center justify-between gap-2"><h2 className="text-[15px] font-bold">Lead Response Overview</h2><span className="dash-total">Total</span></div>
        <div className="mt-3 flex items-center gap-3 max-sm:flex-col 2xl:gap-5"><div className="w-[48%] max-w-[225px] max-sm:w-[200px]"><Donut values={responses} caption="Total Response" /></div><div className="flex min-w-0 flex-1 flex-col gap-5 max-sm:w-full"><Legend values={responses} /><div className="dash-valid-callout"><Check className="size-4 shrink-0" aria-hidden /><span className="flex-1">Valid Lead</span><strong className="tabular">{formatNumber(row.valid)}</strong><span className="text-label tabular">{percent(row.valid, row.total)}</span></div></div></div>
      </section>
      <section className="dash-card min-w-0 p-5" aria-label="Lead Status Breakdown"><div className="flex items-center justify-between gap-2"><h2 className="text-[15px] font-bold">Lead Status Breakdown</h2><span className="dash-total">Total</span></div><StatusBars row={row} /></section>
      <section className="dash-card min-w-0 p-5" aria-label="Buyer Type"><h2 className="text-[15px] font-bold">Buyer Type</h2><div className="mt-3 flex items-center gap-3 max-sm:flex-col"><div className="w-[48%] max-w-[225px] max-sm:w-[200px]"><Donut values={buyers} caption="Total Calls" /></div><Legend values={buyers} /></div><p className="mt-3 flex items-center gap-2 text-[12px]"><span className="size-2.5 rounded-full bg-[#9156e8]" />B2B Matching <strong className="ml-auto tabular">{formatNumber(row.b2b_matching)}</strong><span className="text-label">{percent(row.b2b_matching, row.total)}</span></p><p className="mt-1 text-[11px] text-label">B2B Matching may overlap buyer types.</p></section>
    </div>
    {daily.isPending || sources.isPending ? <Skeleton className="h-[420px]" /> : daily.isError || sources.isError ? <ErrorState error={daily.error ?? sources.error} onRetry={() => { void daily.refetch(); void sources.refetch(); }} /> : <SourceDetail key={`${s.from}:${s.to}`} from={s.from} to={s.to} total={row} daily={daily.data.rows} rows={sources.data.rows} sources={sources.data.keys} />}
  </div>;
}
