import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FileUp, UserPlus, X } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { type ChoiceData, type Condition, type Op } from "@/features/leads/conditions";
import { ConditionChips, FilterButton } from "@/features/leads/filter-button";
import { type LeadItem, leadFilterOptionsQuery, leadSourcesQuery } from "@/features/leads/queries";
import { LeadViewSwitch } from "@/features/leads/view-switch";
import { can, useMe } from "@/lib/auth";
import { countryName } from "@/lib/countries";
import { useEdition } from "@/lib/edition";
import { relative } from "@/lib/format";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { FilterBar, SelectFilter, TextFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const condition = z.object({
  field: z.string(),
  op: z.string() as z.ZodType<Op>,
  value: z.union([z.string(), z.number(), z.boolean(), z.array(z.string())]).optional(),
});

const search = z.object({
  // The board's "more" link carries its search box here.
  q: z.string().optional(),
  // Per-field row (Frappe standard filters): text matches anywhere in the field.
  code: z.string().optional(),
  name: z.string().optional(),
  email: z.string().optional(),
  phone: z.string().optional(),
  company: z.string().optional(),
  // Exhibition Type (edition) filter; absent means every edition the user can read.
  edition: z.string().optional(),
  telemarketing_status: z.string().optional(),
  // A user id, or "none" for unassigned leads.
  owner: z.string().optional(),
  // Stacked conditions from the Filter button.
  f: z.array(condition).optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});
type Search = z.infer<typeof search>;

/** The per-field row and the Filter button, as one list of conditions for the API. */
function conditions(s: Search): Condition[] {
  const text: [string, string | undefined][] = [
    ["registration_code", s.code],
    ["first_name", s.name],
    ["email", s.email],
    ["company_name", s.company],
    // Phone matches digits only; under 4 digits would match almost everything.
    ["phone", s.phone && s.phone.replace(/\D/g, "").length >= 4 ? s.phone : undefined],
  ];
  return [
    ...text.filter(([, v]) => v).map(([field, value]) => ({ field, op: "contains" as const, value })),
    ...(s.f ?? []),
  ];
}

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
  const filterOptions = useQuery(leadFilterOptionsQuery(s.edition));
  const choiceData: ChoiceData = {
    leadSources: (sources.data ?? []).map((o) => ({ id: o.id, name: o.is_active ? o.name : `${o.name} (inactive)` })),
    countries: filterOptions.data?.countries ?? [],
    owners: filterOptions.data?.owners ?? [],
    teams: filterOptions.data?.teams ?? [],
  };
  const conds = conditions(s);
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
              lead_owner_id: s.owner && s.owner !== "none" ? s.owner : undefined,
              unassigned: s.owner === "none" ? true : undefined,
              filters: conds.length ? JSON.stringify(conds) : undefined,
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
  const filtered = Boolean(s.edition || s.q || s.telemarketing_status || s.owner || conds.length);
  const clear = () => void navigate({ search: { page: 1, page_size: s.page_size }, replace: true });
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
        <FilterBar active={filtered} onClear={clear}>
          <TextFilter label="Registration ID" value={s.code} onChange={(code) => set({ code })} />
          <TextFilter label="Name" value={s.name} onChange={(name) => set({ name })} />
          <TextFilter label="Email" value={s.email} onChange={(email) => set({ email })} inputMode="email" />
          <TextFilter label="Phone" value={s.phone} onChange={(phone) => set({ phone })} inputMode="tel" />
          <TextFilter label="Company" value={s.company} onChange={(company) => set({ company })} />
          <SelectFilter className="min-w-[128px]" label="Exhibition Type" value={s.edition} onChange={(v) => { setSelected(new Set()); set({ edition: v, owner: undefined }); }} options={editions.map((e) => ({ value: e.id, label: e.code }))} />
          <SelectFilter className="min-w-[128px]" label="Status" value={s.telemarketing_status} onChange={(v) => set({ telemarketing_status: v })} options={options("telemarketing_status")} />
          <SelectFilter className="min-w-[128px]" label="Lead Owner" allLabel="Anyone" value={s.owner} onChange={(owner) => set({ owner })} options={[{ value: "none", label: "Unassigned" }, ...choiceData.owners.map((o) => ({ value: o.id, label: o.name }))]} />
          <FilterButton value={s.f ?? []} onChange={(f) => set({ f: f.length ? f : undefined })} data={choiceData} />
        </FilterBar>
        {s.q ? (
          <div className="flex items-center gap-2 border-b border-line px-4 py-2 text-[12px]">
            <span className="text-label">Search from the board:</span>
            <span className="flex items-center gap-1 rounded-full bg-input py-0.5 pr-1 pl-2.5">
              {s.q}
              <button type="button" onClick={() => set({ q: undefined })} className="grid size-5 place-items-center rounded-full text-label hover:bg-hover hover:text-ink pointer-coarse:size-8" aria-label={`Remove search: ${s.q}`}>
                <X className="size-3.5" aria-hidden />
              </button>
            </span>
          </div>
        ) : null}
        <ConditionChips value={s.f ?? []} onChange={(f) => set({ f: f.length ? f : undefined })} data={choiceData} />
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
              <EmptyState title="No leads match these filters." action={<Button onClick={clear}>Clear Filters</Button>} />
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
