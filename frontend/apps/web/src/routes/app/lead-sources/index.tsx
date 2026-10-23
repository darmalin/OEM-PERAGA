import { type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { leadSourcesQuery } from "@/features/leads/queries";
import { can, useMe } from "@/lib/auth";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/lead-sources/")({ component: Sources });

const COLUMNS: Column<Schemas["LeadSourceOut"]>[] = [
  { key: "name", header: "Name", cell: (s) => s.name },
  { key: "order", header: "Sort Order", hideBelow: "md", cell: (s) => <span className="tabular">{s.sort_order}</span> },
  { key: "status", header: "Status", cell: (s) => <Indicator value={s.is_active ? "ACTIVE" : "INACTIVE"} text={s.is_active ? "Active" : "Inactive"} /> },
];

function Sources() {
  const me = useMe();
  const q = useQuery(leadSourcesQuery(true));
  const manage = can(me, "exhibition.manage");
  const add = manage ? <Button asChild variant="primary"><Link to="/app/lead-sources/new">Add Source</Link></Button> : undefined;
  return (
    <Page>
      <PageHead title="Sources" meta="Master data for the Source select on visitor leads, shared by every edition." actions={add} />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No sources yet." action={add} />}>
          {(rows) => <ListTable caption="Sources" rows={rows} columns={COLUMNS} rowKey={(s) => s.id} rowLink={manage ? (s) => ({ to: "/app/lead-sources/$sourceId", params: { sourceId: s.id } }) : undefined} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
