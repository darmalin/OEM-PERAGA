import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { can, useMe } from "@/lib/auth";
import { Button } from "@/ui/button";
import { FilterBar, SearchFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/exhibitions/")({
  validateSearch: z.object({ q: z.string().optional(), page: z.number().int().min(1).default(1), page_size: z.number().int().default(20) }),
  component: Exhibitions,
});

function Exhibitions() {
  const me = useMe();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const q = useQuery({
    queryKey: ["exhibitions", s],
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/exhibitions", { params: { query: s } })),
  });
  const manage = can(me, "exhibition.manage");
  const columns: Column<Schemas["ExhibitionOut"]>[] = [
    { key: "code", header: "Code", cell: (e) => <span className="tabular">{e.code}</span> },
    { key: "name", header: "Name", cell: (e) => e.name },
    { key: "active", header: "Status", cell: (e) => <Indicator value={e.is_active ? "ACTIVE" : "CLOSED"} text={e.is_active ? "Active" : "Inactive"} /> },
  ];
  return (
    <Page>
      <PageHead title="Exhibitions" meta="Each exhibition runs one edition per year." actions={manage ? <Button asChild variant="primary"><Link to="/app/exhibitions/new">Add Exhibition</Link></Button> : null} />
      <Panel>
        <FilterBar><SearchFilter value={s.q} onChange={(v) => void navigate({ search: (p) => ({ ...p, q: v, page: 1 }) })} placeholder="Code or name" label="Search exhibitions" /></FilterBar>
        <ListBody query={q} onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })} onPageSize={(page_size) => void navigate({ search: (p) => ({ ...p, page_size, page: 1 }) })} empty={<EmptyState title="No exhibitions yet." action={manage ? <Button asChild variant="primary"><Link to="/app/exhibitions/new">Add Exhibition</Link></Button> : undefined} />}>
          {(items) => <ListTable caption="Exhibitions" rows={items} columns={columns} rowKey={(e) => e.id} rowLink={(e) => ({ to: "/app/exhibitions/$exhibitionId", params: { exhibitionId: e.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
