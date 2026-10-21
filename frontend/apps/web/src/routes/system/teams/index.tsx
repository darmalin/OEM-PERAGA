import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { Button } from "@/ui/button";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/system/teams/")({ component: Teams });

function Teams() {
  const q = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const columns: Column<Schemas["TeamOut"]>[] = [
    { key: "name", header: "Team", cell: (t) => t.name },
    { key: "members", header: "Members", cell: (t) => <span className="tabular">{t.member_ids.length}</span> },
  ];
  return (
    <Page>
      <PageHead title="Teams" meta="Telemarketing teams. A manager with Team scope sees the leads of their team's agents." actions={<Button asChild variant="primary"><Link to="/system/teams/new">Add Team</Link></Button>} />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No teams yet." action={<Button asChild variant="primary"><Link to="/system/teams/new">Add Team</Link></Button>} />}>
          {(rows) => <ListTable caption="Teams" rows={rows} columns={columns} rowKey={(t) => t.id} rowLink={(t) => ({ to: "/system/teams/$teamId", params: { teamId: t.id } })} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
