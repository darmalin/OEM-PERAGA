import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FileUp, UserPlus } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { filterQuery, hasFilters, LeadFilterChips, LeadFilterFields, leadFilterSearch } from "@/features/leads/lead-filters";
import { type LeadItem } from "@/features/leads/queries";
import { LeadViewSwitch } from "@/features/leads/view-switch";
import { can, useMe } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { countryName } from "@/lib/countries";
import { useEdition } from "@/lib/edition";
import { relative } from "@/lib/format";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { FilterBar, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const search = z.object({
  ...leadFilterSearch,
  telemarketing_status: z.string().optional(),
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

  const query = useQuery({
    queryKey: ["leads", s],
    enabled: editions.length > 0,
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET("/api/v1/visitor-leads", {
          params: {
            query: {
              ...filterQuery(s, me.user.id),
              telemarketing_status: s.telemarketing_status ? [s.telemarketing_status as "NEW"] : undefined,
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
  const filtered = Boolean(s.telemarketing_status) || hasFilters(s);
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
          <LeadFilterFields
            s={s}
            set={(patch) => {
              if ("edition" in patch) setSelected(new Set());
              set(patch);
            }}
          >
            <SelectFilter className={cn("min-w-[128px]", !s.telemarketing_status && "max-sm:hidden")} label="Status" value={s.telemarketing_status} onChange={(v) => set({ telemarketing_status: v })} options={options("telemarketing_status")} />
          </LeadFilterFields>
        </FilterBar>
        <LeadFilterChips s={s} set={set} />
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
