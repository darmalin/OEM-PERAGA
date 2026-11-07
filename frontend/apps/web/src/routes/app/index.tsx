import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { RefreshCw } from "lucide-react";
import { useId, useState } from "react";
import { z } from "zod";

import { ReferenceOverview } from "@/features/dashboard/overview";
import { OverviewOperations } from "@/features/dashboard/overview-operations";
import { ExhibitorPipelinePanel } from "@/features/exhibitors/pipeline-panel";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { formatDateTime } from "@/lib/format";
import { EditionBand } from "@/ui/band";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Input } from "@/ui/input";
import { Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, NoEdition, Skeleton } from "@/ui/states";

const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const Route = createFileRoute("/app/")({ validateSearch: z.object({ from: date.optional(), to: date.optional() }), component: Overview });

export function overviewRange(timezone: string, now = new Date()) {
  const to = new Intl.DateTimeFormat("en-CA", { timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  const from = new Date(Date.parse(`${to}T00:00:00Z`) - 29 * 864e5).toISOString().slice(0, 10);
  return { from, to };
}

function Overview() {
  const me = useMe();
  const { edition } = useEdition();
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const client = useQueryClient();
  if (!edition) return <Page><NoEdition /></Page>;
  // Sales pipeline of the edition, for anyone who reads exhibitor leads (counted in their scope).
  const exhibitors = can(me, "exhibitor_lead.read") ? <div className="mt-6"><ExhibitorPipelinePanel editionId={edition.id} /></div> : null;
  if (!can(me, "report.view")) {
    return (
      <Page className="pt-4">
        <PageHead title="Overview" edition />
        <EditionBand edition={edition} />
        {can(me, "telemarketing.call") ? (
          <div className="mt-6"><QueuePreview editionId={edition.id} timezone={edition.timezone} /></div>
        ) : exhibitors ? null : (
          <div className="mt-6"><Panel><EmptyState title="Your role has no overview numbers. Use the menu to open your pages." /></Panel></div>
        )}
        {exhibitors}
      </Page>
    );
  }
  const defaults = overviewRange(edition.timezone);
  const s = { from: search.from ?? defaults.from, to: search.to ?? defaults.to, edition: edition.id };
  const span = (Date.parse(`${s.to}T00:00:00Z`) - Date.parse(`${s.from}T00:00:00Z`)) / 864e5;
  const valid = Number.isFinite(span) && span >= 0 && span < 366;
  return <Page className="max-w-none">
    <PageHead title="Overview" edition meta={`${edition.code} · ${edition.name} · ${edition.timezone}`} actions={<Button onClick={() => { void client.invalidateQueries({ queryKey: ["dashboard"] }); void client.invalidateQueries({ queryKey: ["report", edition.id, "ATTENDANCE"] }); }}><RefreshCw aria-hidden />Refresh</Button>} />
    <div className="mb-4"><OverviewDates key={`${s.from}:${s.to}`} from={s.from} to={s.to} onApply={range => void navigate({ search: range, replace: true })} /></div>
    {valid ? <ReferenceOverview s={s}><OverviewOperations s={s} /></ReferenceOverview> : <p role="alert" className="rounded-[10px] border border-line bg-bg p-5 text-[13px] text-required">Choose a valid date range of up to 366 days.</p>}
    {exhibitors}
  </Page>;
}

function OverviewDates({ from, to, onApply }: { from: string; to: string; onApply: (range: { from: string; to: string }) => void }) {
  const [draft, setDraft] = useState({ from, to });
  const id = useId();
  return <form aria-label="Overview date range" className="dashboard-reference dash-card flex flex-wrap items-center gap-3 px-5 py-3" onSubmit={e => { e.preventDefault(); onApply(draft); }}>
    <label htmlFor={`${id}-from`} className="flex items-center gap-2 text-[12px] text-muted">From<Input id={`${id}-from`} className="w-[148px]" type="date" required value={draft.from} max={draft.to} onChange={e => setDraft({ ...draft, from: e.target.value })} /></label>
    <label htmlFor={`${id}-to`} className="flex items-center gap-2 text-[12px] text-muted">To<Input id={`${id}-to`} className="w-[148px]" type="date" required value={draft.to} min={draft.from} onChange={e => setDraft({ ...draft, to: e.target.value })} /></label>
    <Button type="submit" className="dash-apply">Apply</Button>
    <p className="text-[12px] text-label">All numbers use this exhibition type and date range.</p>
  </form>;
}

function QueuePreview({ editionId, timezone }: { editionId: string; timezone: string }) {
  const q = useQuery({
    queryKey: ["my-queue", editionId, 1, 5],
    queryFn: () => call(api.GET("/api/v1/telemarketing/my-queue", { params: { query: { edition_id: editionId, page: 1, page_size: 5 } } })),
  });
  return (
    <Panel className="xl:col-span-2">
      <PanelHeader title="Who do I call next?" actions={<Button asChild size="sm" variant="primary"><Link to="/app/visitor-leads" search={{ owner: "me", edition: editionId }}>Open My Leads</Link></Button>} />
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
