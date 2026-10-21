import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { can, useMe } from "@/lib/auth";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/system/roles/")({ component: Roles });

function Roles() {
  const me = useMe();
  const q = useQuery({ queryKey: ["roles"], queryFn: () => call(api.GET("/api/v1/roles")) });
  const columns: Column<Schemas["RoleOut"]>[] = [
    { key: "name", header: "Role", cell: (r) => r.name },
    { key: "desc", header: "Description", hideBelow: "lg", cell: (r) => <span className="text-muted">{r.description ?? ""}</span> },
    { key: "perms", header: "Permissions", cell: (r) => <span className="tabular">{r.permissions.length}</span> },
    { key: "kind", header: "Type", hideBelow: "md", cell: (r) => <Indicator value={r.is_system ? "REGISTERED" : "DRAFT"} text={r.is_system ? "Baseline" : "Custom"} /> },
  ];
  return (
    <Page>
      <PageHead title="Roles" meta="A role is a set of permissions. Scope is chosen when the role is given to a user." actions={can(me, "role.manage") ? <Button asChild variant="primary"><Link to="/system/roles/new">Add Role</Link></Button> : null} />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No roles." />}>
          {(rows) => <ListTable caption="Roles" rows={rows} columns={columns} rowKey={(r) => r.id} rowLink={(r) => ({ to: "/system/roles/$roleId", params: { roleId: r.id } })} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
