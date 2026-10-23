import type { Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { cn } from "@/lib/cn";
import { formatDateTime, formatNumber } from "@/lib/format";
import { label } from "@/lib/labels";
import { Indicator } from "@/ui/indicator";
import { ErrorState, Skeleton } from "@/ui/states";

import { type DashboardSearch, emailReportQuery } from "./api";
import { Breakdown } from "./cards";
import { dayLabel, isWeekend } from "./metrics";

type Job = Schemas["EmailReportJob"];
const rate = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 1000) / 10}%` : "0%");

function Tile({ title, value, hint }: { title: string; value: number; hint: string }) {
  return (
    <div className="min-w-0 rounded-[10px] border border-line bg-bg px-4 py-3">
      <p className="truncate text-[12px] text-label">{title}</p>
      <p className="mt-0.5 text-[22px] leading-7 font-semibold tracking-[-0.01em] tabular">{formatNumber(value)}</p>
      <p className="truncate text-[12px] text-label">{hint}</p>
    </div>
  );
}

/** The Email Report tab: emails about leads (QR, reminders) in the user's editions. */
export function EmailReport({ s }: { s: DashboardSearch }) {
  const q = useQuery(emailReportQuery(s));
  if (q.isPending) return <Skeleton className="h-[400px]" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const { totals: t, days, by_status, waiting, recent_failed } = q.data;
  const statusRow = Object.fromEntries(by_status.map((c) => [c.key ?? "", c.count]));
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Tile title="Queued in Period" value={t.queued} hint="Emails put in the queue" />
        <Tile title="Sent Successfully" value={t.sent} hint={`${rate(t.sent, t.queued)} success rate`} />
        <Tile title="Failed" value={t.failed} hint={`${rate(t.failed, t.queued)} failure rate`} />
        <Tile title="Waiting to Send" value={t.waiting_now} hint={`${formatNumber(t.waiting)} from this period`} />
        <Tile title="Sending Now" value={t.sending_now} hint="Being sent at this moment" />
        <Tile title="Sent Today" value={t.sent_today} hint={`Today, ${dayLabel(q.data.today)}`} />
        <Tile title="Retried" value={t.retried} hint="Needed more than one attempt" />
        <Tile title="Cancelled" value={t.cancelled} hint="QR revoked before sending" />
        <Tile title="Email by API" value={t.by_api} hint="Registrations made through the API" />
        <Tile title="All Time" value={t.all_time} hint="Every lead email on record" />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section className="rounded-[12px] border border-line bg-bg" aria-label="Daily email sending">
          <h2 className="border-b border-line px-5 py-3 text-[14px] font-semibold">Daily Email Sending</h2>
          <div className="max-h-[520px] overflow-auto">
            <table className="w-full min-w-[520px] border-collapse text-[13px]">
              <caption className="sr-only">Emails per day</caption>
              <thead className="sticky top-0 bg-bg">
                <tr className="border-b border-line text-left text-[12px] text-label">
                  <th scope="col" className="px-4 py-2 font-medium">Date</th>
                  {["Queued", "Sent", "Failed", "Waiting", "Success Rate"].map((h) => <th key={h} scope="col" className="px-4 py-2 text-right font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {days.map((d) => (
                  <tr key={d.day} className={cn("border-b border-line", isWeekend(d.day) && "bg-[color-mix(in_srgb,var(--red-bg)_55%,transparent)]")}>
                    <th scope="row" className="px-4 py-2 text-left font-normal whitespace-nowrap">{dayLabel(d.day)}</th>
                    <td className="px-4 py-2 text-right tabular">{d.queued ? formatNumber(d.queued) : ""}</td>
                    <td className="px-4 py-2 text-right tabular">{d.sent ? formatNumber(d.sent) : ""}</td>
                    <td className="px-4 py-2 text-right tabular">{d.failed ? formatNumber(d.failed) : ""}</td>
                    <td className="px-4 py-2 text-right tabular">{d.waiting ? formatNumber(d.waiting) : ""}</td>
                    <td className="px-4 py-2 text-right tabular">{d.queued ? rate(d.sent, d.queued) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <Breakdown
          title="Queue Status Breakdown"
          values={["SENT", "QUEUED", "SENDING", "FAILED", "CANCELLED"].map((k) => ({ key: k, label: label("email_status", k), value: statusRow[k] ?? 0 }))}
        />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <JobList title="Waiting to Send" empty="No emails are waiting to send." jobs={waiting} />
        <JobList title="Recent Failed Emails" empty="No failed emails." jobs={recent_failed} showError />
      </div>
    </div>
  );
}

function JobList({ title, empty, jobs, showError }: { title: string; empty: string; jobs: Job[]; showError?: boolean }) {
  return (
    <section className="rounded-[12px] border border-line bg-bg" aria-label={title}>
      <h2 className="border-b border-line px-5 py-3 text-[14px] font-semibold">{title}</h2>
      {jobs.length === 0 ? (
        <p className="px-5 py-6 text-[13px] text-label">{empty}</p>
      ) : (
        <ul className="divide-y divide-line">
          {jobs.map((j) => (
            <li key={j.id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 px-5 py-3 text-[13px]">
              <Link to="/system/email-log/$jobId" params={{ jobId: j.id }} className="truncate font-medium hover:underline">
                {j.lead_name ?? j.recipient}
              </Link>
              <Indicator value={j.status} group="email_status" />
              <span className="truncate text-label">{j.recipient} · {label("email_kind", j.kind)}</span>
              <span className="text-[12px] text-label tabular">{formatDateTime(j.queued_at)}</span>
              {showError && j.error_summary ? <span className="col-span-2 text-[12px] text-red-fg">{j.error_summary}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
