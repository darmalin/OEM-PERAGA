import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { useReport } from "@/features/reports";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { formatDateTime, formatPercent } from "@/lib/format";
import { label } from "@/lib/labels";
import { EditionBand } from "@/ui/band";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { BarList, Metric } from "@/ui/metric";
import { Page, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, NoEdition, Skeleton } from "@/ui/states";

export const Route = createFileRoute("/app/")({ component: Overview });

function Overview() {
  const me = useMe();
  const { edition } = useEdition();
  if (!edition) {
    return (
      <Page>
        <NoEdition />
      </Page>
    );
  }
  const reports = can(me, "report.view");
  return (
    <Page className="pt-6">
      <EditionBand edition={edition}>{reports ? <BandNumbers editionId={edition.id} /> : null}</EditionBand>
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        {reports ? (
          <>
            <TelemarketingPanel editionId={edition.id} />
            <div className="flex flex-col gap-6">
              <RegistrationPanel editionId={edition.id} />
              <GatePanel editionId={edition.id} timezone={edition.timezone} />
            </div>
          </>
        ) : can(me, "telemarketing.call") ? (
          <QueuePreview editionId={edition.id} timezone={edition.timezone} />
        ) : (
          <Panel>
            <EmptyState title="Your role has no overview numbers. Use the menu to open your pages." />
          </Panel>
        )}
      </div>
    </Page>
  );
}

function BandNumbers({ editionId }: { editionId: string }) {
  const leads = useReport("LEADS", editionId, {}, { poll: true });
  const reg = useReport("REGISTRATION", editionId, {}, { poll: true });
  const att = useReport("ATTENDANCE", editionId, {}, { poll: true });
  if (leads.isPending || reg.isPending || att.isPending) {
    return (
      <div className="grid grid-cols-2 gap-6 md:grid-cols-4" role="status" aria-label="Loading numbers">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-12 w-full opacity-30" />
        ))}
      </div>
    );
  }
  if (leads.isError || reg.isError) return <p className="text-[13px] text-on-band-muted">Numbers could not be loaded.</p>;
  return (
    <div className="grid grid-cols-2 gap-6 border-t border-white/15 pt-5 md:grid-cols-4">
      <Metric tone="band" label="Visitor leads" value={leads.data.total} hint={`${leads.data.unassigned} unassigned`} />
      <Metric tone="band" label="Registered" value={reg.data.registered} hint={`${reg.data.qr_active} with an active QR`} />
      <Metric tone="band" label="Unique visitors at the gate" value={att.data?.unique_event_visitors ?? 0} hint={`${att.data?.valid_entries ?? 0} valid entries`} />
      <Metric tone="band" label="Not registered yet" value={reg.data.not_registered} />
    </div>
  );
}

function TelemarketingPanel({ editionId }: { editionId: string }) {
  const tm = useReport("TELEMARKETING", editionId, {}, { poll: true });
  const agents = useReport("AGENTS", editionId, {}, { poll: true });
  return (
    <Panel>
      <PanelHeader title="Who is behind on calls?" actions={<Button asChild size="sm" variant="ghost"><Link to="/app/reports">Open Reports</Link></Button>} />
      {tm.isPending ? (
        <div className="p-5"><Skeleton className="h-32 w-full" /></div>
      ) : tm.isError ? (
        <ErrorState error={tm.error} onRetry={() => void tm.refetch()} />
      ) : (
        <div className="p-5">
          <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
            <Metric label="Call attempts" value={tm.data.attempts} />
            <Metric label="Answer rate" value={formatPercent(tm.data.answer_rate)} />
            <Metric label="Follow-ups due today" value={tm.data.followups_due_today} />
            <Metric label="Follow-ups overdue" value={tm.data.followups_overdue} />
          </div>
          <div className="mt-6">
            <p className="mb-2 text-[12px] text-label">Agents, by open follow-ups and answered calls</p>
            {agents.data && agents.data.agents.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <caption className="sr-only">Agent performance</caption>
                  <thead>
                    <tr className="border-b border-line text-left text-[12px] text-label">
                      <th scope="col" className="py-2 pr-4 font-normal">Agent</th>
                      <th scope="col" className="py-2 pr-4 text-right font-normal">Leads</th>
                      <th scope="col" className="py-2 pr-4 text-right font-normal">Attempts</th>
                      <th scope="col" className="py-2 pr-4 text-right font-normal">Answered</th>
                      <th scope="col" className="py-2 text-right font-normal">Follow-ups done</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.data.agents.map((a) => (
                      <tr key={a.agent_id} className="border-b border-line last:border-b-0">
                        <td className="py-2 pr-4">{a.full_name}</td>
                        <td className="py-2 pr-4 text-right tabular">{a.leads_owned}</td>
                        <td className="py-2 pr-4 text-right tabular">{a.attempts}</td>
                        <td className="py-2 pr-4 text-right tabular">{a.answered}</td>
                        <td className="py-2 text-right tabular">
                          {a.followups_done} / {a.followups_total}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-[13px] text-muted">No calls logged yet. Assign leads to agents to start.</p>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

function RegistrationPanel({ editionId }: { editionId: string }) {
  const reg = useReport("REGISTRATION", editionId, {}, { poll: true });
  return (
    <Panel>
      <PanelHeader title="Did the QR emails go out?" actions={<Button asChild size="sm" variant="ghost"><Link to="/app/registrations">Open Registrations</Link></Button>} />
      <div className="p-5">
        {reg.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : reg.isError ? (
          <ErrorState error={reg.error} />
        ) : reg.data.emails_by_status.length === 0 ? (
          <p className="text-[13px] text-muted">No QR emails yet. They are sent when a visitor is registered.</p>
        ) : (
          <>
            <BarList rows={reg.data.emails_by_status} labelFor={(k) => label("email_status", k)} />
            <p className="mt-4 text-[12px] text-label">Sent means the mail server accepted the email; bounces are not tracked yet.</p>
          </>
        )}
      </div>
    </Panel>
  );
}

function GatePanel({ editionId, timezone }: { editionId: string; timezone: string }) {
  const gates = useReport("GATES", editionId, {}, { poll: true });
  return (
    <Panel>
      <PanelHeader title="Gate activity" actions={<Button asChild size="sm" variant="ghost"><Link to="/app/scans">Scan History</Link></Button>} />
      <div className="p-5">
        {gates.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : gates.isError ? (
          <ErrorState error={gates.error} />
        ) : gates.data.by_gate.length === 0 ? (
          <p className="text-[13px] text-muted">No gates set up for this edition yet.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-line">
            {gates.data.by_gate.map((g) => (
              <li key={g.gate_id} className="flex items-center justify-between gap-3 py-2 text-[13px]">
                <span className="truncate">
                  <span className="font-medium">{g.gate_code}</span> <span className="text-label">{g.gate_name}</span>
                </span>
                <span className="tabular text-muted">
                  {g.valid_entries} valid · {g.rejected} rejected
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-[12px] text-label">Times in {timezone}. Refreshes every 30 seconds.</p>
      </div>
    </Panel>
  );
}

function QueuePreview({ editionId, timezone }: { editionId: string; timezone: string }) {
  const q = useQuery({
    queryKey: ["my-queue", editionId, 1, 5],
    queryFn: () => call(api.GET("/api/v1/telemarketing/my-queue", { params: { query: { edition_id: editionId, page: 1, page_size: 5 } } })),
  });
  return (
    <Panel className="xl:col-span-2">
      <PanelHeader title="Who do I call next?" actions={<Button asChild size="sm" variant="primary"><Link to="/app/my-calls">Open My Calls</Link></Button>} />
      {q.isPending ? (
        <div className="p-5"><Skeleton className="h-24 w-full" /></div>
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : q.data.items.length === 0 ? (
        <EmptyState title="No leads are assigned to you yet. Your manager assigns leads from the Visitor Leads list." />
      ) : (
        <ul className="divide-y divide-line">
          {q.data.items.map((l) => (
            <li key={l.id} className="flex items-center justify-between gap-3 px-5 py-3 text-[13px]">
              <Link to="/app/visitor-leads/$leadId" params={{ leadId: l.id }} className="truncate font-medium hover:underline">
                {l.first_name} <span className="font-normal text-label tabular">{l.registration_code}</span>
              </Link>
              <span className="flex items-center gap-3">
                {l.next_followup_at ? <span className="text-label tabular">Follow up {formatDateTime(l.next_followup_at, timezone)}</span> : null}
                <Indicator value={l.telemarketing_status} group="telemarketing_status" />
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
