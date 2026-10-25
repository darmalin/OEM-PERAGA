import { api, call } from "@ems/api";
import { keepPreviousData, useQueries } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { BoardColumn } from "@/features/leads/board-column";
import { filterQuery, hasFilters, LeadFilterChips, LeadFilterFields, leadFilterSchema, pickFilters } from "@/features/leads/lead-filters";
import { LeadViewSwitch } from "@/features/leads/view-switch";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { BOARD_COLUMNS, type TmStatus } from "@/lib/transitions";
import { Button } from "@/ui/button";
import { FilterBar } from "@/ui/filters";
import { Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

const search = leadFilterSchema;
type Search = z.infer<typeof search>;

export const Route = createFileRoute("/app/visitor-leads/board")({
  validateSearch: search,
  component: LeadBoard,
});

/** Cards per column; the column links to the full list when there are more. */
const PER_COLUMN = 50;

function LeadBoard() {
  const me = useMe();
  const { editions } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<Search>) => void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });

  const columns = useQueries({
    queries: BOARD_COLUMNS.map((status) => ({
      queryKey: ["leads", "board", status, s],
      placeholderData: keepPreviousData,
      queryFn: () =>
        call(
          api.GET("/api/v1/visitor-leads", {
            params: {
              query: {
                ...filterQuery(s, me.user.id, true),
                telemarketing_status: [status],
                page: 1,
                page_size: PER_COLUMN,
                sort: "-updated_at",
              },
            },
          }),
        ),
    })),
  });

  if (editions.length === 0) return <Page><NoEdition /></Page>;
  const filtered = hasFilters(s);
  const canMove = can(me, "telemarketing.call");
  const onMove = (leadId: string, to?: TmStatus) =>
    void navigate({ to: "/app/visitor-leads/$leadId/log-call", params: { leadId }, search: { to, from: "board" } });

  return (
    <Page className="max-w-none">
      <PageHead
        title="Visitor Leads"
        meta={canMove ? "Drag a card to the next status, or use its menu. Each move logs a call with its verification; calls that keep the status go through Log Call." : "Leads by telemarketing status."}
        actions={
          <>
            <LeadViewSwitch current="board" />
            {can(me, "visitor.create") ? (
              <Button asChild variant="primary"><Link to="/app/visitor-leads/new">Add Visitor Lead</Link></Button>
            ) : null}
          </>
        }
      />
      <Panel>
        <FilterBar active={filtered} onClear={() => void navigate({ search: {}, replace: true })}>
          <LeadFilterFields s={s} set={set} board />
        </FilterBar>
        <LeadFilterChips s={s} set={set} board />
        <div className="flex gap-3 overflow-x-auto p-4" role="list" aria-label="Status columns">
          {BOARD_COLUMNS.map((status, i) => (
            <BoardColumn
              key={status}
              status={status}
              query={columns[i]!}
              editions={editions}
              canMove={canMove}
              onMove={onMove}
              moreLink={{ to: "/app/visitor-leads", search: { ...pickFilters(s), telemarketing_status: status, page: 1, page_size: 20 } }}
            />
          ))}
        </div>
      </Panel>
    </Page>
  );
}
