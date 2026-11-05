import { api, call } from "@ems/api";
import { keepPreviousData, useQueries, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { LayoutGrid, Loader2, Plus, UserRound } from "lucide-react";
import { useState } from "react";

import { type BoardMove, boardMoves } from "@/features/exhibitors/board-moves";
import { type ExhibitorLead, STAGES } from "@/features/exhibitors/queries";
import { ExhibitorViewSwitch } from "@/features/exhibitors/view-switch";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { relative } from "@/lib/format";
import { cn } from "@/lib/cn";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuTrigger } from "@/ui/menu";
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

type Stage = (typeof STAGES)[number];
type Perms = { update: boolean; invite: boolean };
type OnMove = (lead: ExhibitorLead, move: BoardMove) => void;
const DRAG_TYPE = "application/x-ems-exhibitor-lead";

/** The card being dragged, so every column can tell whether it accepts the drop. */
let dragging: { lead: ExhibitorLead; moves: BoardMove[] } | null = null;

const moveText = (lead: ExhibitorLead, m: BoardMove) =>
  m.to === "EXHIBITOR" ? (m.kind === "booth-page" ? "Exhibitor (choose a booth first)" : "Exhibitor (Convert)") : m.to === "LEAD" && lead.stage === "LOST" ? "Lead (reopen)" : label("sales_stage", m.to);

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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState<string | null>(null);
  const perms: Perms = { update: can(me, "exhibitor_lead.update"), invite: can(me, "exhibitor.invite") };
  if (!edition) return <Page><NoEdition /></Page>;

  const onMove: OnMove = (lead, m) => {
    const params = { leadId: lead.id };
    if (m.kind === "stage-page") {
      void navigate({ to: "/app/exhibitor-leads/$leadId/stage", params, search: { to: m.to as "LEAD" | "OPPORTUNITY" | "LOST" } });
    } else if (m.kind === "booth-page") {
      void navigate({ to: "/app/exhibitor-leads/$leadId/booth", params });
    } else if (m.kind === "convert-page") {
      void navigate({ to: "/app/exhibitor-leads/$leadId/convert", params });
    } else {
      setMoving(lead.id);
      call(api.POST("/api/v1/exhibitor-leads/{lead_id}/stage", { params: { path: { lead_id: lead.id } }, body: { stage: m.to as "LEAD" | "OPPORTUNITY", version: lead.version } }))
        .then((updated) => notifySuccess(`Moved to ${label("sales_stage", updated.stage)}`, updated.company_name))
        .catch(notifyError)
        .finally(() => {
          setMoving(null);
          void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
        });
    }
  };

  return (
    <Page className="max-w-none">
      <PageHead
        edition
        title="Exhibitor Leads"
        meta={perms.update ? "Drag a card to another stage, or use its menu. Lost asks for a reason; Exhibitor goes through Convert." : "Leads by sales stage."}
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
            <Column key={stage} stage={stage} query={columns[i]!} perms={perms} onMove={onMove} moving={moving} />
          ))}
        </div>
      </Panel>
    </Page>
  );
}

function Column({ stage, query, perms, onMove, moving }: { stage: Stage; query: UseQueryResult<PageOf<ExhibitorLead>>; perms: Perms; onMove: OnMove; moving: string | null }) {
  const [over, setOver] = useState<"ok" | "no" | null>(null);
  const target = () => dragging?.moves.find((m) => m.to === stage) ?? null;
  const total = query.data?.total ?? 0;
  return (
    <section
      role="listitem"
      aria-label={`${label("sales_stage", stage)}, ${total} ${total === 1 ? "lead" : "leads"}`}
      className={cn("flex w-[280px] shrink-0 flex-col rounded-[12px] bg-subtle max-md:w-[85vw]", over === "ok" && "outline-2 outline-focus", over === "no" && "opacity-60")}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes(DRAG_TYPE) || dragging?.lead.stage === stage) return;
        const ok = target() !== null;
        setOver(ok ? "ok" : "no");
        if (ok) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }
      }}
      onDragLeave={() => setOver(null)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(null);
        const m = target();
        if (dragging && m) onMove(dragging.lead, m);
      }}
    >
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
          query.data.items.map((l) => <Card key={l.id} lead={l} moves={boardMoves(l, perms)} onMove={onMove} busy={moving === l.id} />)
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

function Card({ lead, moves, onMove, busy }: { lead: ExhibitorLead; moves: BoardMove[]; onMove: OnMove; busy: boolean }) {
  return (
    <article
      draggable={moves.length > 0 && !busy}
      onDragStart={(e) => {
        dragging = { lead, moves };
        e.dataTransfer.setData(DRAG_TYPE, lead.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragEnd={() => {
        dragging = null;
      }}
      aria-busy={busy}
      className={cn("relative rounded-[10px] border border-line bg-bg text-[13px]", moves.length > 0 && "cursor-grab active:cursor-grabbing", busy && "opacity-60")}
    >
      <div className="flex items-start gap-2 border-b border-line px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <Link to="/app/exhibitor-leads/$leadId" params={{ leadId: lead.id }} className="block truncate font-medium text-ink hover:underline">
            {lead.company_name}
          </Link>
          <p className="truncate text-[12px] text-label">{lead.contact_name}</p>
        </div>
        {busy ? <Loader2 className="mt-0.5 size-4 animate-spin text-label" aria-label="Moving" /> : null}
        {moves.length > 0 && !busy ? (
          <Menu>
            <MenuTrigger asChild>
              <Button size="icon" variant="ghost" className="-mt-1 -mr-1.5 size-7" aria-label={`Move ${lead.company_name}`}>
                <Plus aria-hidden />
              </Button>
            </MenuTrigger>
            <MenuContent>
              <MenuLabel>Move to</MenuLabel>
              {moves.map((m) => (
                <MenuItem key={m.to} onSelect={() => onMove(lead, m)}>{moveText(lead, m)}</MenuItem>
              ))}
            </MenuContent>
          </Menu>
        ) : null}
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
