import type { Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { gatesQuery } from "@/features/gate/queries";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/gates/")({ component: Gates });

function Gates() {
  const me = useMe();
  const { edition } = useEdition();
  const q = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  if (!edition) return <Page><NoEdition /></Page>;
  const manage = can(me, "gate.manage_devices");
  const columns: Column<Schemas["GateOut"]>[] = [
    { key: "code", header: "Code", cell: (g) => <span className="tabular">{g.code}</span> },
    { key: "name", header: "Name", cell: (g) => g.name },
    { key: "status", header: "Status", cell: (g) => <Indicator value={g.is_active ? "ACTIVE" : "CLOSED"} text={g.is_active ? "Open" : "Closed"} /> },
  ];
  return (
    <Page>
      <PageHead title="Gates" meta={`Entrances of ${edition.code}. Each scanner device belongs to one gate.`} actions={manage ? <Button asChild variant="primary"><Link to="/app/gates/new">Add Gate</Link></Button> : null} />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No gates yet. Add a gate, then register scanner devices for it." action={manage ? <Button asChild variant="primary"><Link to="/app/gates/new">Add Gate</Link></Button> : undefined} />}>
          {(rows) => <ListTable caption="Gates" rows={rows} columns={columns} rowKey={(g) => g.id} rowLink={manage ? (g) => ({ to: "/app/gates/$gateId", params: { gateId: g.id } }) : undefined} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
