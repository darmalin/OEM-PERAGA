import { api, call } from "@ems/api";
import { keepPreviousData, useQueries } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { BoardColumn } from "@/features/leads/board-column";
import { LeadViewSwitch } from "@/features/leads/view-switch";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { BOARD_COLUMNS, type TmStatus } from "@/lib/transitions";
import { Button } from "@/ui/button";
import { FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

const search = z.object({
  q: z.string().optional(),
  edition: z.string().optional(),
  mine: z.boolean().optional(),
});
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
                edition_id: s.edition,
                q: s.q,
                telemarketing_status: [status],
                lead_owner_id: s.mine ? me.user.id : undefined,
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
  const filtered = Boolean(s.q || s.edition || s.mine);
  const canMove = can(me, "telemarketing.call");
  const onMove = (leadId: string, to: TmStatus) =>
    void navigate({ to: "/app/visitor-leads/$leadId/log-call", params: { leadId }, search: { to, from: "board" } });

  return (
    <Page className="max-w-none">
      <PageHead
        title="Visitor Leads"
        meta={canMove ? "Drag a card to the next status, or use its Move menu. Each move logs a call with its verification." : "Leads by telemarketing status."}
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
          <SearchFilter value={s.q} onChange={(q) => set({ q })} placeholder="Name, email, phone, company, Registration ID" label="Search leads" />
          <SelectFilter label="Exhibition Type" value={s.edition} onChange={(edition) => set({ edition })} options={editions.map((e) => ({ value: e.id, label: e.code }))} />
          <SelectFilter label="Lead Owner" allLabel="Anyone" value={s.mine ? "me" : undefined} onChange={(v) => set({ mine: v === "me" ? true : undefined })} options={[{ value: "me", label: "Assigned to me" }]} />
        </FilterBar>
        <div className="flex gap-3 overflow-x-auto p-4" role="list" aria-label="Status columns">
          {BOARD_COLUMNS.map((status, i) => (
            <BoardColumn
              key={status}
              status={status}
              query={columns[i]!}
              editions={editions}
              canMove={canMove}
              onMove={onMove}
              moreLink={{ to: "/app/visitor-leads", search: { telemarketing_status: status, q: s.q, page: 1, page_size: 20 } }}
            />
          ))}
        </div>
      </Panel>
    </Page>
  );
}
