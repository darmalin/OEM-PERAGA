import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Check, Clock3, Mail, ScanLine, Users, X } from "lucide-react";
import type { ComponentType } from "react";

import { useReport } from "@/features/reports";
import { formatNumber } from "@/lib/format";
import { Button } from "@/ui/button";
import { ErrorState, Skeleton } from "@/ui/states";

import { emailReportQuery, type DashboardSearch } from "./api";

function OperationCard({ label, value, hint, tone, icon: Icon }: { label: string; value: number; hint: string; tone: string; icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }> }) {
  return <div className="dash-card relative min-w-0 px-5 py-4" aria-label={label}>
    <span className={`dash-icon dash-icon-${tone}`}><Icon className="size-5" aria-hidden /></span>
    <p className="pr-10 text-[12px] text-muted">{label}</p>
    <p className="mt-1 text-[27px] leading-8 font-bold tracking-tight tabular">{formatNumber(value)}</p>
    <p className="mt-3 text-[12px] text-label">{hint}</p>
  </div>;
}

/** Accepted scans count people once; email totals concern lead emails queued in this range. */
export function OverviewOperations({ s }: { s: DashboardSearch & { edition: string } }) {
  const scans = useReport("ATTENDANCE", s.edition, { date_from: s.from, date_to: s.to }, { poll: true });
  const emails = useQuery(emailReportQuery(s));
  return <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
    <section className="min-w-0" aria-label="Visitor Scans">
      <div className="mb-3 flex items-center justify-between gap-2"><h2 className="text-[15px] font-bold">Visitor Scans</h2><Button asChild size="sm" variant="ghost"><Link to="/app/scans">Scan History</Link></Button></div>
      {scans.isPending ? <Skeleton className="h-[280px]" /> : scans.isError ? <ErrorState error={scans.error} onRetry={() => void scans.refetch()} /> : <div className="grid grid-cols-2 gap-3">
        <OperationCard label="Visitors Scanned" value={scans.data.unique_event_visitors} hint="Unique people; repeat scans count once" tone="green" icon={Users} />
        <OperationCard label="Valid Scans" value={scans.data.valid_entries} hint="All accepted entries, including repeats" tone="blue" icon={ScanLine} />
        <OperationCard label="Repeat Scans" value={scans.data.repeat_entries} hint="Accepted entries after the first entry of a day" tone="amber" icon={ScanLine} />
        <OperationCard label="Rejected Scans" value={scans.data.rejected} hint="Excluded from the visitors scanned total" tone="red" icon={X} />
      </div>}
    </section>
    <section className="min-w-0" aria-label="Lead Emails">
      <div className="mb-3 flex items-center justify-between gap-2"><h2 className="text-[15px] font-bold">Lead Emails</h2><Button asChild size="sm" variant="ghost"><Link to="/app/dashboard" search={{ tab: "email", from: s.from, to: s.to, edition: s.edition }}>Email Report</Link></Button></div>
      {emails.isPending ? <Skeleton className="h-[280px]" /> : emails.isError ? <ErrorState error={emails.error} onRetry={() => void emails.refetch()} /> : <div className="grid grid-cols-2 gap-3">
        <OperationCard label="Emails Sent" value={emails.data.totals.sent} hint="Accepted by the mail server" tone="green" icon={Check} />
        <OperationCard label="Emails Waiting" value={emails.data.totals.waiting} hint="Queued or currently sending" tone="amber" icon={Clock3} />
        <OperationCard label="Emails Failed" value={emails.data.totals.failed} hint="Emails that could not be sent" tone="red" icon={X} />
        <OperationCard label="Total Emails" value={emails.data.totals.queued} hint="Lead emails queued in this period" tone="blue" icon={Mail} />
      </div>}
    </section>
  </div>;
}
