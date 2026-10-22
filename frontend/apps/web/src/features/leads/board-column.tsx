import type { Schemas } from "@ems/api";
import type { UseQueryResult } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { MoveRight } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/cn";
import { label } from "@/lib/labels";
import { moves, type TmStatus } from "@/lib/transitions";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "@/ui/menu";
import { ErrorState, Skeleton } from "@/ui/states";

import type { LeadItem } from "./queries";

type Page = Schemas["Page_LeadListItem_"];
type Edition = Schemas["EditionBrief"];
const DRAG_TYPE = "application/x-ems-lead";

/** Status of the card being dragged; set on drag start so every column can light up. */
let dragging: { leadId: string; from: TmStatus } | null = null;

export function BoardColumn({
  status,
  query,
  editions,
  canMove,
  onMove,
  moreLink,
}: {
  status: TmStatus;
  query: UseQueryResult<Page>;
  editions: Edition[];
  canMove: boolean;
  /** `to` undefined: open Log Call without a target (the status may stay). */
  onMove: (leadId: string, to?: TmStatus) => void;
  moreLink: { to: "/app/visitor-leads"; search: Record<string, unknown> };
}) {
  const [over, setOver] = useState<"ok" | "no" | null>(null);
  const accepts = () => dragging !== null && moves(dragging.from).some((m) => m.to === status);
  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;

  return (
    <section
      role="listitem"
      aria-label={`${label("telemarketing_status", status)}, ${total} ${total === 1 ? "lead" : "leads"}`}
      className={cn(
        "flex w-[272px] shrink-0 flex-col rounded-[12px] bg-subtle",
        over === "ok" && "outline-2 outline-focus",
        over === "no" && "opacity-60",
      )}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes(DRAG_TYPE)) return;
        const ok = accepts();
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
        if (dragging && accepts()) onMove(dragging.leadId, status);
      }}
    >
      <header className="flex items-center justify-between gap-2 px-3 pt-3 pb-2">
        <Indicator value={status} group="telemarketing_status" />
        <span className="text-[12px] text-label tabular">{total.toLocaleString("en")}</span>
      </header>
      <div className="flex min-h-[120px] flex-col gap-2 px-2 pb-2">
        {query.isPending ? (
          <>
            <Skeleton className="h-[76px]" />
            <Skeleton className="h-[76px]" />
          </>
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        ) : items.length === 0 ? (
          <p className="px-2 py-6 text-center text-[13px] text-label">No leads</p>
        ) : (
          items.map((l) => (
            <Card key={l.id} lead={l} edition={editions.find((e) => e.id === l.edition_id)} canMove={canMove} onMove={onMove} />
          ))
        )}
        {total > items.length ? (
          <Link to={moreLink.to} search={moreLink.search as never} className="rounded-[6px] px-2 py-1.5 text-center text-[13px] text-link hover:underline">
            {(total - items.length).toLocaleString("en")} more in the list
          </Link>
        ) : null}
      </div>
    </section>
  );
}

function Card({ lead, edition, canMove, onMove }: { lead: LeadItem; edition?: Edition; canMove: boolean; onMove: (leadId: string, to?: TmStatus) => void }) {
  const targets = canMove ? moves(lead.telemarketing_status) : [];
  return (
    <article
      draggable={targets.length > 0}
      onDragStart={(e) => {
        dragging = { leadId: lead.id, from: lead.telemarketing_status };
        e.dataTransfer.setData(DRAG_TYPE, lead.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      onDragEnd={() => {
        dragging = null;
      }}
      className={cn("rounded-[8px] border border-line bg-bg p-3 text-[13px]", targets.length > 0 && "cursor-grab active:cursor-grabbing")}
    >
      <div className="flex items-start justify-between gap-2">
        <Link to="/app/visitor-leads/$leadId" params={{ leadId: lead.id }} className="min-w-0 font-medium text-ink hover:underline">
          <span className="block truncate">{lead.first_name}</span>
        </Link>
        {canMove ? (
          <Menu>
            <MenuTrigger asChild>
              <Button size="icon" variant="ghost" className="-mt-1 -mr-1 size-7" aria-label={`Move or log a call for ${lead.first_name}`}>
                <MoveRight aria-hidden />
              </Button>
            </MenuTrigger>
            <MenuContent>
              {targets.length > 0 ? <MenuLabel>Move to</MenuLabel> : null}
              {targets.map((m) => (
                <MenuItem key={m.to} onSelect={() => onMove(lead.id, m.to)}>
                  {label("telemarketing_status", m.to)}
                  <span className="ml-auto text-[12px] text-label">{m.answered ? "answered" : "not answered"}</span>
                </MenuItem>
              ))}
              {targets.length > 0 ? <MenuSeparator /> : null}
              {/* Calls that leave the status as it is (e.g. Answer, then not answered). */}
              <MenuItem onSelect={() => onMove(lead.id)}>Log Call</MenuItem>
            </MenuContent>
          </Menu>
        ) : null}
      </div>
      {lead.company_name ? <p className="truncate text-label">{lead.company_name}</p> : null}
      {/* The Registration ID starts with the edition code, so it also shows the Exhibition Type. */}
      <p className="mt-2 truncate text-[12px] text-label tabular" title={edition?.name}>{lead.registration_code}</p>
      <p className="truncate text-[12px] text-label">{lead.lead_owner_name ?? "Unassigned"}</p>
    </article>
  );
}
