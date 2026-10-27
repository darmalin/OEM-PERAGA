import type { Schemas } from "@ems/api";
import type { UseQueryResult } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { CalendarClock, Phone, Plus, QrCode } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/cn";
import { relative } from "@/lib/format";
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
            <Skeleton className="h-[180px]" />
            <Skeleton className="h-[180px]" />
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

/** First letter of a name for the round avatar ("Đinh" -> "Đ"). */
const initial = (name: string | null | undefined) => (name?.trim().charAt(0) || "?").toUpperCase();

function Avatar({ name, square }: { name: string | null | undefined; square?: boolean }) {
  return (
    <span aria-hidden className={cn("grid size-5 shrink-0 place-items-center bg-input text-[11px] font-medium text-muted", square ? "rounded-[5px]" : "rounded-full")}>
      {initial(name)}
    </span>
  );
}

const shortDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

/** Frappe CRM style card: name, company, contact, owner, last change, then counts and actions. */
function Card({ lead, edition, canMove, onMove }: { lead: LeadItem; edition?: Edition; canMove: boolean; onMove: (leadId: string, to?: TmStatus) => void }) {
  const targets = canMove ? moves(lead.telemarketing_status) : [];
  const [now] = useState(Date.now); // read once: a card does not tick while it is open
  const followup = lead.next_followup_at ? new Date(lead.next_followup_at) : null;
  const overdue = followup !== null && followup.getTime() < now;
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
      className={cn("relative rounded-[10px] border border-line bg-bg text-[13px]", targets.length > 0 && "cursor-grab active:cursor-grabbing")}
    >
      <div className="flex items-center gap-2 border-b border-line px-3 py-2.5">
        <Avatar name={lead.first_name} />
        <Link to="/app/visitor-leads/$leadId" params={{ leadId: lead.id }} className="min-w-0 font-medium text-ink hover:underline">
          <span className="block truncate">{lead.first_name}</span>
        </Link>
      </div>
      <div className="flex flex-col gap-1.5 px-3 py-2.5">
        {lead.company_name ? (
          <p className="flex min-w-0 items-center gap-2" title={lead.company_name}>
            <Avatar name={lead.company_name} square />
            <span className="truncate">{lead.company_name}</span>
          </p>
        ) : null}
        {lead.email ? <p className="truncate" title={lead.email}>{lead.email}</p> : null}
        {lead.phone ? <p className="truncate tabular">{lead.phone}</p> : null}
        <p className="flex min-w-0 items-center gap-2">
          {lead.lead_owner_name ? (
            <>
              <Avatar name={lead.lead_owner_name} />
              <span className="truncate">{lead.lead_owner_name}</span>
            </>
          ) : (
            <span className="text-label">Unassigned</span>
          )}
        </p>
        {/* The Registration ID starts with the edition code, so it also shows the Exhibition Type. */}
        <p className="flex items-center justify-between gap-2 text-[12px] text-label">
          <span className="truncate tabular" title={edition?.name}>{lead.registration_code}</span>
          <span className="shrink-0" title={`Updated ${lead.updated_at}`}>{relative(lead.updated_at)}</span>
        </p>
      </div>
      <div className="flex items-center gap-3 border-t border-line px-3 py-1.5 text-[12px] text-label">
        <span className="flex items-center gap-1" title={`${lead.call_attempts} ${lead.call_attempts === 1 ? "call" : "calls"}`}>
          <Phone className="size-3.5" aria-hidden />
          <span className="tabular">{lead.call_attempts}</span>
          <span className="sr-only">{lead.call_attempts === 1 ? "call" : "calls"}</span>
        </span>
        <span className={cn("flex items-center gap-1", overdue && "text-[var(--red-fg)]")} title={followup ? `Next follow-up ${followup.toLocaleString()}${overdue ? " (overdue)" : ""}` : "No follow-up"}>
          <CalendarClock className="size-3.5" aria-hidden />
          <span className="tabular">{followup ? shortDate.format(followup) : "–"}</span>
          <span className="sr-only">{followup ? (overdue ? "follow-up overdue" : "next follow-up") : "no follow-up"}</span>
        </span>
        <span className={cn("flex items-center gap-1", lead.qr_status === "ACTIVE" && "text-[var(--green-fg)]")} title={label("qr_status", lead.qr_status)}>
          <QrCode className="size-3.5" aria-hidden />
          <span className="sr-only">{label("qr_status", lead.qr_status)}</span>
        </span>
        {canMove ? (
          <Menu>
            <MenuTrigger asChild>
              <Button size="icon" variant="ghost" className="ml-auto size-7" aria-label={`Actions for ${lead.first_name}`}>
                <Plus aria-hidden />
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
    </article>
  );
}
