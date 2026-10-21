import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { can, useMe } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { FilterBar, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/editions/")({
  validateSearch: z.object({ status: z.string().optional(), page: z.number().int().min(1).default(1), page_size: z.number().int().default(20) }),
  component: Editions,
});

function Editions() {
  const me = useMe();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const q = useQuery({
    queryKey: ["editions", s],
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/editions", { params: { query: s as never } })),
  });
  const columns: Column<Schemas["EditionOut"]>[] = [
    { key: "code", header: "Code", cell: (e) => <span className="tabular">{e.code}</span> },
    { key: "name", header: "Name", cell: (e) => e.name },
    { key: "dates", header: "Dates", hideBelow: "md", cell: (e) => <span className="tabular text-muted">{formatDate(e.start_date)} to {formatDate(e.end_date)}</span> },
    { key: "city", header: "City", hideBelow: "lg", cell: (e) => e.city ?? "" },
    { key: "status", header: "Status", cell: (e) => <Indicator value={e.status} group="edition_status" /> },
  ];
  return (
    <Page>
      <PageHead title="Editions" meta="One edition per exhibition per year; all event data belongs to an edition." actions={can(me, "edition.manage") ? <Button asChild variant="primary"><Link to="/app/editions/new" search={{}}>Add Edition</Link></Button> : null} />
      <Panel>
        <FilterBar><SelectFilter label="Status" value={s.status} onChange={(v) => void navigate({ search: (p) => ({ ...p, status: v, page: 1 }) })} options={options("edition_status")} /></FilterBar>
        <ListBody query={q} onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })} onPageSize={(page_size) => void navigate({ search: (p) => ({ ...p, page_size, page: 1 }) })} empty={<EmptyState title="No editions you can see." />}>
          {(items) => <ListTable caption="Editions" rows={items} columns={columns} rowKey={(e) => e.id} rowLink={(e) => ({ to: "/app/editions/$editionId", params: { editionId: e.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
