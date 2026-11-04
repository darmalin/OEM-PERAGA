import { api, call } from "@ems/api";
import { keepPreviousData, useQueries, type UseQueryResult } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { LayoutGrid, UserRound } from "lucide-react";

import { type ExhibitorLead, STAGES } from "@/features/exhibitors/queries";
import { ExhibitorViewSwitch } from "@/features/exhibitors/view-switch";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { relative } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, NoEdition, Skeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/board")({ component: ExhibitorBoard });

/** Cards per column; the column links to the filtered list when there are more. */
const PER_COLUMN = 50;

interface PageOf<T> {
  items: T[];
  total: number;
}

function ExhibitorBoard() {
  const me = useMe();
  const { edition } = useEdition();
  const columns = useQueries({
    queries: STAGES.map((stage) => ({
      queryKey: ["exhibitor-leads", edition?.id, "board", stage],
      enabled: Boolean(edition),
      placeholderData: keepPreviousData,
      queryFn: () =>
        call(
          api.GET("/api/v1/exhibitor-leads", {
            params: { query: { edition_id: edition!.id, stage: [stage], page: 1, page_size: PER_COLUMN, sort: "-updated_at" } },
          }),
        ),
    })),
  });
  if (!edition) return <Page><NoEdition /></Page>;

  return (
    <Page className="max-w-none">
      <PageHead
        edition
        title="Exhibitor Leads"
        meta="Leads by sales stage. Open a card to move its stage, pick a booth, or convert it."
        actions={
          <>
            <ExhibitorViewSwitch current="board" />
            {can(me, "exhibitor_lead.create") ? (
              <Button asChild variant="primary"><Link to="/app/exhibitor-leads/new">Add Exhibitor Lead</Link></Button>
            ) : null}
          </>
        }
      />
      <Panel>
        <div className="flex gap-3 overflow-x-auto p-4" role="list" aria-label="Stage columns">
          {STAGES.map((stage, i) => (
            <Column key={stage} stage={stage} query={columns[i]!} />
          ))}
        </div>
      </Panel>
    </Page>
  );
}

function Column({ stage, query }: { stage: (typeof STAGES)[number]; query: UseQueryResult<PageOf<ExhibitorLead>> }) {
  const total = query.data?.total ?? 0;
  return (
    <section role="listitem" aria-label={label("sales_stage", stage)} className="flex w-[280px] shrink-0 flex-col rounded-[12px] bg-subtle max-md:w-[85vw]">
      <header className="flex items-center justify-between gap-2 px-3 pt-3 pb-2">
        <Indicator value={stage} group="sales_stage" />
        <span className="text-[12px] text-label tabular">{total.toLocaleString("en")}</span>
      </header>
      <div className="flex min-h-[120px] flex-col gap-2 px-2 pb-2">
        {query.isPending ? (
          <>
            <Skeleton className="h-[120px]" />
            <Skeleton className="h-[120px]" />
          </>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <p className="px-2 py-6 text-center text-[13px] text-label">No leads</p>
        ) : (
          query.data.items.map((l) => <Card key={l.id} lead={l} />)
        )}
        {total > PER_COLUMN ? (
          <Link to="/app/exhibitor-leads" search={{ stage, page: 1, page_size: 20 }} className="rounded-[6px] px-2 py-1.5 text-center text-[13px] text-link hover:underline">
            {(total - PER_COLUMN).toLocaleString("en")} more in the list
          </Link>
        ) : null}
      </div>
    </section>
  );
}

function Card({ lead }: { lead: ExhibitorLead }) {
  return (
    <article className="relative rounded-[10px] border border-line bg-bg text-[13px]">
      <div className="border-b border-line px-3 py-2.5">
        <Link to="/app/exhibitor-leads/$leadId" params={{ leadId: lead.id }} className="block truncate font-medium text-ink hover:underline">
          {lead.company_name}
        </Link>
        <p className="truncate text-[12px] text-label">{lead.contact_name}</p>
      </div>
      <div className="flex flex-col gap-1.5 px-3 py-2.5 text-muted">
        <p className="flex items-center gap-2">
          <LayoutGrid className="size-3.5 shrink-0 text-label" aria-hidden />
          <span className="sr-only">Booth</span>
          {lead.booth_code ? <span className="tabular text-ink">{lead.booth_code}</span> : <span className="text-label">No booth</span>}
        </p>
        <p className="flex min-w-0 items-center gap-2">
          <UserRound className="size-3.5 shrink-0 text-label" aria-hidden />
          <span className="sr-only">Lead owner</span>
          {lead.lead_owner_name ? <span className="truncate">{lead.lead_owner_name}</span> : <span className="text-label">Unassigned</span>}
        </p>
        <p className="text-[12px] text-label" title={`Updated ${lead.updated_at}`}>{relative(lead.updated_at)}</p>
      </div>
    </article>
  );
}
