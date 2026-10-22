import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { FileDown } from "lucide-react";
import type { ReactNode } from "react";
import { z } from "zod";

import { gatesQuery } from "@/features/gate/queries";
import { type ReportName, useReport } from "@/features/reports";
import { can, useMe } from "@/lib/auth";
import { countryName } from "@/lib/countries";
import { useEdition } from "@/lib/edition";
import { formatDate, formatDateTime, formatNumber, formatPercent } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { DateFilter, FilterBar, SelectFilter } from "@/ui/filters";
import { BarList, Metric } from "@/ui/metric";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, NoEdition, Skeleton } from "@/ui/states";

const REPORTS: { v: ReportName; t: string; q: string }[] = [
  { v: "LEADS", t: "Leads", q: "How many leads do we have, and where from?" },
  { v: "TELEMARKETING", t: "Telemarketing", q: "Are calls getting answered, and are follow-ups on time?" },
  { v: "VERIFICATION", t: "Verification", q: "How many leads are valid, and who said they will attend?" },
  { v: "REGISTRATION", t: "Registration", q: "Who is registered, through which channel, and did the QR emails go out?" },
  { v: "AGENTS", t: "Agents", q: "How is each agent doing?" },
  { v: "ATTENDANCE", t: "Attendance", q: "How many people came in, and how many came back?" },
  { v: "GATES", t: "Gates", q: "Which gates are busy, and when?" },
  { v: "IMPORTS", t: "Imports", q: "How did the Excel imports go?" },
  { v: "EMAILS", t: "Emails", q: "Did our emails get sent?" },
];

const search = z.object({
  report: z.enum(["LEADS", "TELEMARKETING", "VERIFICATION", "REGISTRATION", "AGENTS", "ATTENDANCE", "GATES", "IMPORTS", "EMAILS"]).default("LEADS"),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  gate_id: z.string().optional(),
});

export const Route = createFileRoute("/app/reports")({ validateSearch: search, component: Reports });

function Reports() {
  const me = useMe();
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const queryClient = useQueryClient();
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const params = { date_from: s.date_from, date_to: s.date_to, gate_id: s.gate_id };
  const report = useReport(s.report, edition?.id ?? null, params);
  if (!edition) return <Page><NoEdition /></Page>;
  const meta = REPORTS.find((r) => r.v === s.report)!;
  const dated = !["LEADS", "VERIFICATION"].includes(s.report);
  const gated = s.report === "ATTENDANCE" || s.report === "GATES";

  const exportReport = async () => {
    try {
      await call(api.POST("/api/v1/exports/reports", { body: { edition_id: edition.id, report: s.report, ...params } }));
      void queryClient.invalidateQueries({ queryKey: ["exports"] });
      notifySuccess("Report export started", "Download it from Exports when it is ready.");
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <Page>
      <PageHead edition
        title="Reports"
        meta={report.data ? `${edition.code} · generated ${formatDateTime(report.data.generated_at, edition.timezone)}` : edition.code}
        actions={can(me, "report.export") ? <Button onClick={() => void exportReport()}><FileDown aria-hidden />Export to Excel</Button> : null}
      />
      <Panel>
        <div className="flex gap-5 overflow-x-auto border-b border-line px-5" role="tablist" aria-label="Report">
          {REPORTS.map((r) => (
            <button
              key={r.v}
              role="tab"
              aria-selected={s.report === r.v}
              onClick={() => void navigate({ search: (p) => ({ ...p, report: r.v }) })}
              className="-mb-px h-11 border-b-2 border-transparent text-[13px] whitespace-nowrap text-label hover:text-ink aria-selected:border-ink aria-selected:font-medium aria-selected:text-ink"
            >
              {r.t}
            </button>
          ))}
        </div>
        {dated || gated ? (
          <FilterBar active={Boolean(s.date_from || s.date_to || s.gate_id)} onClear={() => void navigate({ search: { report: s.report } })}>
            {dated ? <DateFilter label="From" value={s.date_from} onChange={(v) => void navigate({ search: (p) => ({ ...p, date_from: v }) })} /> : null}
            {dated ? <DateFilter label="To" value={s.date_to} onChange={(v) => void navigate({ search: (p) => ({ ...p, date_to: v }) })} /> : null}
            {gated ? <SelectFilter label="Gate" value={s.gate_id} onChange={(v) => void navigate({ search: (p) => ({ ...p, gate_id: v }) })} options={(gates.data ?? []).map((g) => ({ value: g.id, label: `${g.code} ${g.name}` }))} /> : null}
          </FilterBar>
        ) : null}
        <div className="p-5">
          <h2 className="mb-5 text-[16px] font-semibold">{meta.q}</h2>
          {report.isPending ? (
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4" role="status" aria-label="Loading report">
              {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : report.isError ? (
            <ErrorState error={report.error} onRetry={() => void report.refetch()} />
          ) : (
            <ReportBody data={report.data as never} name={s.report} />
          )}
          {dated ? <p className="mt-6 text-[12px] text-label">Dates are event-local ({edition.timezone}), both ends included.</p> : null}
        </div>
      </Panel>
    </Page>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-6 md:grid-cols-4">{children}</div>;
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-8">
      <h3 className="mb-3 text-[13px] font-medium text-label">{title}</h3>
      {children}
    </div>
  );
}

function Bars({ rows, group }: { rows: { key: string | null; count: number }[]; group?: Parameters<typeof label>[0] }) {
  if (rows.length === 0) return <p className="text-[13px] text-muted">Nothing recorded yet.</p>;
  return <BarList rows={rows} labelFor={(k) => (k == null ? "Not set" : group ? label(group, k) : k)} />;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- one renderer for nine typed report shapes
function ReportBody({ name, data }: { name: ReportName; data: any }) {
  switch (name) {
    case "LEADS":
      return (
        <>
          <Grid>
            <Metric label="Total leads" value={data.total} />
            <Metric label="New, not called" value={data.new} />
            <Metric label="Assigned" value={data.assigned} />
            <Metric label="Unassigned" value={data.unassigned} />
          </Grid>
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            <Block title="By source"><Bars rows={data.by_source} group="source" /></Block>
            <Block title="By country (top 50)"><BarList rows={data.by_country} labelFor={(k) => (k ? countryName(k) : "Not set")} /></Block>
          </div>
        </>
      );
    case "TELEMARKETING":
      return (
        <>
          <Grid>
            <Metric label="Call attempts" value={data.attempts} />
            <Metric label="Answered" value={data.answered} hint={`Answer rate ${formatPercent(data.answer_rate)}`} />
            <Metric label="Follow-ups due today" value={data.followups_due_today} />
            <Metric label="Follow-ups overdue" value={data.followups_overdue} hint={`${data.followups_open} open in total`} />
          </Grid>
          <Block title="Leads by status"><Bars rows={data.leads_by_status} group="telemarketing_status" /></Block>
        </>
      );
    case "VERIFICATION":
      return (
        <>
          <Grid>
            <Metric label="Valid leads" value={data.valid} />
            <Metric label="Invalid" value={data.invalid} />
            <Metric label="Undecided" value={data.undecided} />
            <Metric label="B2B matching" value={data.b2b_matching} />
          </Grid>
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            <Block title="Attendance intention"><Bars rows={data.by_attend} group="attend" /></Block>
            <Block title="Type of buyers"><Bars rows={data.by_buyer_type} group="buyer_type" /></Block>
          </div>
        </>
      );
    case "REGISTRATION":
      return (
        <>
          <Grid>
            <Metric label="Registered" value={data.registered} />
            <Metric label="Not registered" value={data.not_registered} />
            <Metric label="Active QR" value={data.qr_active} />
            <Metric label="Revoked QR" value={data.qr_revoked} />
          </Grid>
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            <Block title="By channel"><Bars rows={data.by_channel} group="channel" /></Block>
            <Block title="QR emails by status"><Bars rows={data.emails_by_status} group="email_status" /></Block>
          </div>
        </>
      );
    case "AGENTS":
      return data.agents.length === 0 ? (
        <EmptyState title="No agent activity yet." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <caption className="sr-only">Agent performance</caption>
            <thead>
              <tr className="border-b border-line text-left text-[12px] text-label">
                {["Agent", "Leads owned", "Attempts", "Answered", "Follow-ups done", "Completion"].map((h, i) => (
                  <th key={h} scope="col" className={`py-2 pr-4 font-normal ${i > 0 ? "text-right" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.agents.map((a: { agent_id: string; full_name: string; leads_owned: number; attempts: number; answered: number; followups_done: number; followups_total: number; followup_completion: number | null }) => (
                <tr key={a.agent_id} className="border-b border-line last:border-b-0">
                  <td className="py-2 pr-4">{a.full_name}</td>
                  <td className="py-2 pr-4 text-right tabular">{formatNumber(a.leads_owned)}</td>
                  <td className="py-2 pr-4 text-right tabular">{formatNumber(a.attempts)}</td>
                  <td className="py-2 pr-4 text-right tabular">{formatNumber(a.answered)}</td>
                  <td className="py-2 pr-4 text-right tabular">{a.followups_done} / {a.followups_total}</td>
                  <td className="py-2 text-right tabular">{formatPercent(a.followup_completion)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "ATTENDANCE":
      return (
        <>
          <Grid>
            <Metric label="Unique visitors (event)" value={data.unique_event_visitors} />
            <Metric label="First entries" value={data.first_entries} />
            <Metric label="Repeat entries" value={data.repeat_entries} />
            <Metric label="Rejected scans" value={data.rejected} hint={`${formatNumber(data.total_scans)} scans in total`} />
          </Grid>
          <Block title="By day">
            {data.by_day.length === 0 ? <p className="text-[13px] text-muted">No scans yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <caption className="sr-only">Attendance by day</caption>
                  <thead>
                    <tr className="border-b border-line text-left text-[12px] text-label">
                      {["Day", "Unique visitors", "First", "Repeat", "Rejected", "Scans"].map((h, i) => <th key={h} scope="col" className={`py-2 pr-4 font-normal ${i > 0 ? "text-right" : ""}`}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_day.map((d: { local_date: string; unique_visitors: number; first_entries: number; repeat_entries: number; rejected: number; total_scans: number }) => (
                      <tr key={d.local_date} className="border-b border-line last:border-b-0">
                        <td className="py-2 pr-4 tabular">{formatDate(d.local_date)}</td>
                        <td className="py-2 pr-4 text-right tabular">{formatNumber(d.unique_visitors)}</td>
                        <td className="py-2 pr-4 text-right tabular">{formatNumber(d.first_entries)}</td>
                        <td className="py-2 pr-4 text-right tabular">{formatNumber(d.repeat_entries)}</td>
                        <td className="py-2 pr-4 text-right tabular">{formatNumber(d.rejected)}</td>
                        <td className="py-2 text-right tabular">{formatNumber(d.total_scans)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Block>
        </>
      );
    case "GATES": {
      const hours: { local_date: string; hour: number; total_scans: number; valid_entries: number }[] = data.by_hour;
      const max = Math.max(1, ...hours.map((h) => h.total_scans));
      return (
        <>
          <Block title="Scans per gate">
            {data.by_gate.length === 0 ? <p className="text-[13px] text-muted">No gates in this edition yet.</p> : (
              <BarList rows={data.by_gate.map((g: { gate_code: string; gate_name: string; total_scans: number }) => ({ key: `${g.gate_code} · ${g.gate_name}`, count: g.total_scans }))} labelFor={(k) => k ?? ""} />
            )}
          </Block>
          <Block title="Scans per hour (event-local time)">
            {hours.length === 0 ? <p className="text-[13px] text-muted">No scans yet.</p> : (
              <div className="flex h-40 items-end gap-1 overflow-x-auto" role="img" aria-label={`Scans per hour: ${hours.map((h) => `${formatDate(h.local_date)} ${h.hour}:00 ${h.total_scans}`).join(", ")}`}>
                {hours.map((h) => (
                  <div key={`${h.local_date}-${h.hour}`} className="flex min-w-7 flex-1 flex-col items-center gap-1" title={`${formatDate(h.local_date)} ${String(h.hour).padStart(2, "0")}:00, ${h.total_scans} scans, ${h.valid_entries} valid`}>
                    <span className="text-[11px] text-label tabular">{h.total_scans}</span>
                    <div className="w-full rounded-t-[4px] bg-primary" style={{ height: `${(h.total_scans / max) * 110}px` }} />
                    <span className="text-[11px] text-label tabular">{String(h.hour).padStart(2, "0")}</span>
                  </div>
                ))}
              </div>
            )}
          </Block>
        </>
      );
    }
    case "IMPORTS":
      return (
        <>
          <Grid>
            <Metric label="Import jobs" value={data.jobs} />
            <Metric label="Leads created" value={data.created} hint={`${formatNumber(data.processed)} rows processed`} />
            <Metric label="Duplicates" value={data.duplicate} />
            <Metric label="Invalid rows" value={data.invalid} />
          </Grid>
          <Block title="Jobs by status"><Bars rows={data.by_status} group="job_status" /></Block>
        </>
      );
    case "EMAILS":
      return (
        <>
          <Grid><Metric label="Emails" value={data.total} /></Grid>
          <Block title="By status"><Bars rows={data.by_status} group="email_status" /></Block>
          <p className="mt-4 text-[12px] text-label">Sent means the mail server accepted the email; bounces are not tracked yet.</p>
        </>
      );
  }
}
