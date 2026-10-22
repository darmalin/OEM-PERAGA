import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import type { LeadItem } from "@/features/leads/queries";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { formatDateTime, relative } from "@/lib/format";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { FilterBar, SelectFilter } from "@/ui/filters";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/my-calls")({
  validateSearch: z.object({
    view: z.enum(["mine", "team"]).default("mine"),
    agent_id: z.string().optional(),
    page: z.number().int().min(1).default(1),
    page_size: z.number().int().default(20),
  }),
  component: MyCalls,
});

function MyCalls() {
  const me = useMe();
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const team = s.view === "team" && can(me, "telemarketing.view_team");
  const tz = edition?.timezone;

  const agents = useQuery({
    queryKey: ["agents", edition?.id],
    enabled: Boolean(edition) && team && can(me, "visitor.assign"),
    queryFn: () => call(api.GET("/api/v1/visitor-leads/assignable-agents", { params: { query: { edition_id: edition!.id } } })),
  });
  const query = useQuery({
    queryKey: ["my-queue", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET(team ? "/api/v1/telemarketing/team-queue" : "/api/v1/telemarketing/my-queue", {
          params: { query: { edition_id: edition!.id, agent_id: team ? s.agent_id : undefined, page: s.page, page_size: s.page_size } },
        }),
      ),
  });
  if (!edition) return <Page><NoEdition /></Page>;

  const columns: Column<LeadItem>[] = [
    { key: "name", header: "Name", cell: (l) => <>{l.first_name}{l.company_name ? <span className="font-normal text-label"> · {l.company_name}</span> : null}</> },
    { key: "phone", header: "Phone", cell: (l) => <span className="tabular">{l.phone ?? <span className="text-label">No phone</span>}</span> },
    { key: "follow", header: "Follow-up", cell: (l) => (l.next_followup_at ? <span className={new Date(l.next_followup_at) < new Date() ? "font-medium text-[var(--red-fg)] tabular" : "tabular"}>{formatDateTime(l.next_followup_at, tz)}</span> : <span className="text-label">None</span>) },
    { key: "status", header: "Status", cell: (l) => <Indicator value={l.telemarketing_status} group="telemarketing_status" /> },
    ...(team ? [{ key: "owner", header: "Agent", hideBelow: "md" as const, cell: (l: LeadItem) => l.lead_owner_name ?? "" }] : []),
    { key: "last", header: "Last call", hideBelow: "lg", cell: (l) => <span className="text-label">{l.last_call_at ? relative(l.last_call_at) : "Never"}</span> },
  ];

  return (
    <Page>
      <PageHead edition
        title={team ? "Team Calls" : "My Calls"}
        meta="Overdue follow-ups first, then new leads. Open a lead to log the call."
      />
      <Panel>
        {can(me, "telemarketing.view_team") ? (
          <FilterBar>
            <SelectFilter label="Queue" allLabel="My leads" value={s.view === "team" ? "team" : undefined} onChange={(v) => void navigate({ search: { view: v === "team" ? "team" : "mine", page: 1, page_size: s.page_size } })} options={[{ value: "team", label: "My team" }]} />
            {team && agents.data ? (
              <SelectFilter label="Agent" allLabel="Every agent" value={s.agent_id} onChange={(v) => void navigate({ search: (p) => ({ ...p, agent_id: v, page: 1 }) })} options={agents.data.map((a) => ({ value: a.id, label: a.full_name }))} />
            ) : null}
          </FilterBar>
        ) : null}
        <ListBody
          query={query}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => void navigate({ search: (p) => ({ ...p, page_size, page: 1 }) })}
          empty={<EmptyState title={team ? "No leads are assigned to your team yet." : "No leads are assigned to you yet. Your manager assigns them from Visitor Leads."} />}
        >
          {(items) => (
            <ListTable caption="Call queue" rows={items} columns={columns} rowKey={(l) => l.id} rowLink={(l) => ({ to: "/app/visitor-leads/$leadId", params: { leadId: l.id } })} />
          )}
        </ListBody>
      </Panel>
    </Page>
  );
}
