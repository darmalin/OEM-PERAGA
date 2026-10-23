import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FileUp, UserPlus } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { type LeadItem, leadSourcesQuery } from "@/features/leads/queries";
import { LeadViewSwitch } from "@/features/leads/view-switch";
import { can, useMe } from "@/lib/auth";
import { countryName } from "@/lib/countries";
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
  // Exhibition Type (edition) filter; absent means every edition the user can read.
  edition: z.string().optional(),
  telemarketing_status: z.string().optional(),
  registration_status: z.string().optional(),
  source: z.string().optional(),
  lead_source: z.string().optional(),
  validity: z.enum(["VALID", "INVALID"]).optional(),
  unassigned: z.boolean().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});
type Search = z.infer<typeof search>;

export const Route = createFileRoute("/app/visitor-leads/")({
  validateSearch: search,
  component: LeadList,
});

const columns = (editionCode: (id: string) => string | undefined): Column<LeadItem>[] => [
  {
    key: "name",
    header: "Name",
    cell: (l) => (
      <span className="flex flex-col leading-tight">
        <span>{l.first_name}</span>
        {l.company_name ? <span className="text-[12px] font-normal text-label">{l.company_name}</span> : null}
      </span>
    ),
  },
  { key: "code", header: "Registration ID", cell: (l) => <span className="tabular text-muted">{l.registration_code}</span> },
  { key: "edition", header: "Exhibition Type", hideBelow: "lg", cell: (l) => <span className="text-muted">{editionCode(l.edition_id)}</span> },
  { key: "contact", header: "Contact", hideBelow: "xl", cell: (l) => <span className="text-muted">{l.phone ?? l.email ?? ""}</span> },
  { key: "country", header: "Country", hideBelow: "2xl", cell: (l) => countryName(l.country) },
  { key: "status", header: "Status", cell: (l) => <Indicator value={l.telemarketing_status} group="telemarketing_status" /> },
  { key: "reg", header: "Registration", hideBelow: "md", cell: (l) => <Indicator value={l.registration_status} group="registration_status" /> },
  { key: "owner", header: "Lead Owner", hideBelow: "xl", cell: (l) => l.lead_owner_name ?? <span className="text-label">Unassigned</span> },
  { key: "updated", header: "Updated", hideBelow: "lg", className: "text-right", cell: (l) => <span className="text-label tabular" title={l.updated_at}>{relative(l.updated_at)}</span> },
];

function LeadList() {
  const me = useMe();
  const { editions } = useEdition();
  const s = Route.useSearch();
  const edition = editions.find((e) => e.id === s.edition);
  const navigate = useNavigate({ from: Route.fullPath });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const set = (patch: Partial<Search>) =>
    void navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }), replace: true });

  const sources = useQuery(leadSourcesQuery(true));
  const query = useQuery({
    queryKey: ["leads", s],
    enabled: editions.length > 0,
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET("/api/v1/visitor-leads", {
          params: {
            query: {
              edition_id: s.edition,
              q: s.q,
              telemarketing_status: s.telemarketing_status ? [s.telemarketing_status as "NEW"] : undefined,
              registration_status: s.registration_status as "REGISTERED" | undefined,
              source: s.source as "MANUAL" | undefined,
              lead_source_id: s.lead_source,
              is_valid_lead: s.validity === "VALID" ? true : undefined,
              is_invalid: s.validity === "INVALID" ? true : undefined,
              unassigned: s.unassigned,
              page: s.page,
              page_size: s.page_size,
              sort: "-updated_at",
            },
          },
        }),
      ),
  });

  if (editions.length === 0) return <Page><NoEdition /></Page>;
  const where = edition ? edition.code : "all editions";
  const filtered = Boolean(s.lead_source || s.edition || s.q || s.telemarketing_status || s.registration_status || s.source || s.validity || s.unassigned);
  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const items = query.data?.items ?? [];

  return (
    <Page>
      <PageHead
        title="Visitor Leads"
        meta={query.data ? `${query.data.total.toLocaleString("en")} in ${where}${filtered ? " matching the filters" : ""}` : where}
        actions={
          <>
            <LeadViewSwitch current="list" />
            {can(me, "visitor.import") ? (
              <Button asChild>
                <Link to="/app/imports/new"><FileUp aria-hidden />Import Excel</Link>
              </Button>
            ) : null}
            {can(me, "visitor.create") ? (
              <Button asChild variant="primary">
                <Link to="/app/visitor-leads/new">Add Visitor Lead</Link>
              </Button>
            ) : null}
          </>
        }
      />
      <Panel>
        <FilterBar
          active={filtered}
          onClear={() => void navigate({ search: { page: 1, page_size: s.page_size }, replace: true })}
        >
          <SearchFilter value={s.q} onChange={(q) => set({ q })} placeholder="Name, email, phone, company, Registration ID" label="Search leads" />
          <SelectFilter label="Exhibition Type" value={s.edition} onChange={(v) => { setSelected(new Set()); set({ edition: v }); }} options={editions.map((e) => ({ value: e.id, label: e.code }))} />
          <SelectFilter label="Status" value={s.telemarketing_status} onChange={(v) => set({ telemarketing_status: v })} options={options("telemarketing_status")} />
          <SelectFilter label="Registration" value={s.registration_status} onChange={(v) => set({ registration_status: v })} options={options("registration_status")} />
          <SelectFilter label="Source" value={s.lead_source} onChange={(v) => set({ lead_source: v })} options={(sources.data ?? []).map((o) => ({ value: o.id, label: o.is_active ? o.name : `${o.name} (inactive)` }))} />
          <SelectFilter label="Channel" value={s.source} onChange={(v) => set({ source: v })} options={options("source")} />
          <SelectFilter label="Lead Quality" value={s.validity} onChange={(v) => set({ validity: v as Search["validity"] })} options={[{ value: "VALID", label: "Valid" }, { value: "INVALID", label: "Invalid" }]} />
          <SelectFilter label="Lead Owner" allLabel="Anyone" value={s.unassigned ? "none" : undefined} onChange={(v) => set({ unassigned: v === "none" ? true : undefined })} options={[{ value: "none", label: "Unassigned" }]} />
        </FilterBar>
        {selected.size > 0 ? (
          <div className="flex flex-wrap items-center gap-3 border-b border-line bg-subtle px-4 py-2 text-[13px]" role="region" aria-label="Bulk actions">
            <span className="font-medium tabular">{selected.size} selected</span>
            {can(me, "visitor.assign") && edition ? (
              <Button
                size="sm"
                variant="primary"
                onClick={() => void navigate({ to: "/app/visitor-leads/assign", state: { leadIds: [...selected], editionId: edition.id } })}
              >
                <UserPlus aria-hidden />
                Assign To
              </Button>
            ) : can(me, "visitor.assign") ? (
              <span className="text-label">Choose one Exhibition Type to assign leads.</span>
            ) : null}
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>Clear Selection</Button>
          </div>
        ) : null}
        <ListBody
          query={query}
          onPage={(page) => set({ page })}
          onPageSize={(page_size) => set({ page_size })}
          empty={
            filtered ? (
              <EmptyState title="No leads match these filters." action={<Button onClick={() => void navigate({ search: { page: 1, page_size: s.page_size } })}>Clear Filters</Button>} />
            ) : (
              <EmptyState
                title="No visitor leads yet. Import an Excel file or add one by hand."
                action={can(me, "visitor.import") ? <Button asChild variant="primary"><Link to="/app/imports/new">Import Excel</Link></Button> : undefined}
              />
            )
          }
        >
          {() => (
            <ListTable
              caption="Visitor leads"
              rows={items}
              columns={columns((id) => editions.find((e) => e.id === id)?.code)}
              rowKey={(l) => l.id}
              rowLink={(l) => ({ to: "/app/visitor-leads/$leadId", params: { leadId: l.id } })}
              selected={can(me, "visitor.assign") ? selected : undefined}
              onToggle={toggle}
              onToggleAll={(checked) =>
                setSelected((prev) => {
                  const next = new Set(prev);
                  items.forEach((l) => (checked ? next.add(l.id) : next.delete(l.id)));
                  return next;
                })
              }
            />
          )}
        </ListBody>
      </Panel>
    </Page>
  );
}
