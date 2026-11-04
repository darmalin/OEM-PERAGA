import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { formatMoney } from "@/lib/format";
import { Button } from "@/ui/button";
import { FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const SHOW = { available: "Available", held: "Held", inactive: "Include not for sale" } as const;
const search = z.object({
  q: z.string().optional(),
  show: z.enum(["available", "held", "inactive"]).optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(50),
});
type Search = z.infer<typeof search>;

export const Route = createFileRoute("/app/booths/")({ validateSearch: search, component: Booths });

type Booth = Schemas["BoothOut"];

function status(b: Booth) {
  if (!b.is_active) return <Indicator value="INACTIVE" text="Not for Sale" />;
  if (b.is_available) return <Indicator value="ACTIVE" text="Available" />;
  return <Indicator value="OPPORTUNITY" text="Held" />;
}

function Booths() {
  const me = useMe();
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<Search>) => void navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }), replace: true });
  const query = useQuery({
    queryKey: ["booths", edition?.id, "list", s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET("/api/v1/booths", {
          params: {
            query: {
              edition_id: edition!.id,
              q: s.q,
              available: s.show === "available" ? true : s.show === "held" ? false : undefined,
              include_inactive: s.show === "inactive",
              page: s.page,
              page_size: s.page_size,
            },
          },
        }),
      ),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const manage = can(me, "booth.manage");
  const filtered = Boolean(s.q || s.show);
  const clear = () => void navigate({ search: { page: 1, page_size: s.page_size }, replace: true });
  const add = manage ? <Button asChild variant="primary"><Link to="/app/booths/new">Add Booth</Link></Button> : null;
  const columns: Column<Booth>[] = [
    { key: "code", header: "Code", cell: (b) => <span className="tabular">{b.code}</span> },
    { key: "status", header: "Status", cell: status },
    // Only users who see every lead of the edition get the holder (exhibitors/service.py).
    {
      key: "holder",
      header: "Held By",
      hideBelow: "md",
      cell: (b) =>
        b.exhibitor_lead_id ? (
          <Link to="/app/exhibitor-leads/$leadId" params={{ leadId: b.exhibitor_lead_id }} className="text-link hover:underline">{b.exhibitor_company_name}</Link>
        ) : <span className="text-label">{b.is_available ? "" : "Another lead"}</span>,
    },
    { key: "hall", header: "Hall", hideBelow: "lg", cell: (b) => b.hall ?? "" },
    { key: "area", header: "Area", hideBelow: "lg", cell: (b) => <span className="tabular">{Number(b.area_sqm)} m²</span> },
    { key: "price", header: "Price", className: "text-right", cell: (b) => <span className="tabular">{formatMoney(b.price, b.currency)}</span> },
  ];
  return (
    <Page>
      <PageHead
        edition
        title="Booths"
        meta={query.data ? `${query.data.total.toLocaleString("en")} in ${edition.code}${filtered ? " matching the filters" : ""}` : edition.code}
        actions={add}
      />
      <Panel>
        <FilterBar active={filtered} onClear={clear}>
          <SearchFilter value={s.q} onChange={(q) => set({ q })} placeholder="Search booth code or hall" />
          <SelectFilter label="Show" value={s.show} onChange={(v) => set({ show: v as Search["show"] })} allLabel="All for sale" options={Object.entries(SHOW).map(([value, label]) => ({ value, label }))} />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => set({ page })}
          onPageSize={(page_size) => set({ page_size })}
          empty={
            filtered ? (
              <EmptyState title="No booths match these filters." action={<Button onClick={clear}>Clear Filters</Button>} />
            ) : (
              <EmptyState title={`No booths in ${edition.code} yet. Add them from the floor plan.`} action={add ?? undefined} />
            )
          }
        >
          {(rows) => (
            <ListTable
              caption="Booths"
              rows={rows}
              columns={columns}
              rowKey={(b) => b.id}
              rowLink={manage ? (b) => ({ to: "/app/booths/$boothId", params: { boothId: b.id } }) : undefined}
            />
          )}
        </ListBody>
      </Panel>
    </Page>
  );
}
