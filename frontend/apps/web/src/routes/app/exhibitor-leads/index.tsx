import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { type ExhibitorLead, leadOwnersQuery, STAGES } from "@/features/exhibitors/queries";
import { ExhibitorViewSwitch } from "@/features/exhibitors/view-switch";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { relative } from "@/lib/format";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const search = z.object({
  q: z.string().optional(),
  stage: z.enum(STAGES).optional(),
  owner: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});
type Search = z.infer<typeof search>;

export const Route = createFileRoute("/app/exhibitor-leads/")({ validateSearch: search, component: ExhibitorLeadList });

const columns: Column<ExhibitorLead>[] = [
  {
    key: "company",
    header: "Company",
    cell: (l) => (
      <span className="flex flex-col leading-tight">
        <span>{l.company_name}</span>
        <span className="text-[12px] font-normal text-label">{l.contact_name}</span>
      </span>
    ),
  },
  { key: "stage", header: "Stage", cell: (l) => <Indicator value={l.stage} group="sales_stage" /> },
  { key: "booth", header: "Booth", cell: (l) => <span className="tabular">{l.booth_code ?? ""}</span> },
  { key: "contact", header: "Contact", hideBelow: "xl", cell: (l) => <span className="text-muted">{l.email}</span> },
  { key: "owner", header: "Lead Owner", hideBelow: "lg", cell: (l) => l.lead_owner_name ?? <span className="text-label">Unassigned</span> },
  { key: "updated", header: "Updated", hideBelow: "lg", className: "text-right", cell: (l) => <span className="text-label tabular" title={l.updated_at}>{relative(l.updated_at)}</span> },
];

function ExhibitorLeadList() {
  const me = useMe();
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<Search>) => void navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }), replace: true });
  const owners = useQuery({ ...leadOwnersQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const query = useQuery({
    queryKey: ["exhibitor-leads", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET("/api/v1/exhibitor-leads", {
          params: { query: { edition_id: edition!.id, q: s.q, stage: s.stage ? [s.stage] : undefined, lead_owner_id: s.owner, page: s.page, page_size: s.page_size, sort: "-updated_at" } },
        }),
      ),
  });

  if (!edition) return <Page><NoEdition /></Page>;
  const filtered = Boolean(s.q || s.stage || s.owner);
  const clear = () => void navigate({ search: { page: 1, page_size: s.page_size }, replace: true });
  const add = can(me, "exhibitor_lead.create") ? (
    <Button asChild variant="primary"><Link to="/app/exhibitor-leads/new">Add Exhibitor Lead</Link></Button>
  ) : null;

  return (
    <Page>
      <PageHead
        edition
        title="Exhibitor Leads"
        meta={query.data ? `${query.data.total.toLocaleString("en")} in ${edition.code}${filtered ? " matching the filters" : ""}` : edition.code}
        actions={<><ExhibitorViewSwitch current="list" />{add}</>}
      />
      <Panel>
        <FilterBar active={filtered} onClear={clear}>
          <SearchFilter value={s.q} onChange={(q) => set({ q })} placeholder="Search company, contact, email or phone" />
          <SelectFilter label="Stage" value={s.stage} onChange={(v) => set({ stage: v as Search["stage"] })} options={options("sales_stage")} />
          <SelectFilter label="Lead Owner" value={s.owner} onChange={(owner) => set({ owner })} options={(owners.data?.owners ?? []).map((o) => ({ value: o.id, label: o.id === me.user.id ? `${o.full_name} (me)` : o.full_name }))} />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => set({ page })}
          onPageSize={(page_size) => set({ page_size })}
          empty={
            filtered ? (
              <EmptyState title="No exhibitor leads match these filters." action={<Button onClick={clear}>Clear Filters</Button>} />
            ) : (
              <EmptyState title={`No exhibitor leads in ${edition.code} yet.`} action={add ?? undefined} />
            )
          }
        >
          {(rows) => (
            <ListTable
              caption="Exhibitor leads"
              rows={rows}
              columns={columns}
              rowKey={(l) => l.id}
              rowLink={(l) => ({ to: "/app/exhibitor-leads/$leadId", params: { leadId: l.id } })}
            />
          )}
        </ListBody>
      </Panel>
    </Page>
  );
}
