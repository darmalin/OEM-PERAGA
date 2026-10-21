import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { can, useMe } from "@/lib/auth";
import { countryName } from "@/lib/countries";
import { Button } from "@/ui/button";
import { ArrayBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/venues/")({ component: Venues });

function Venues() {
  const me = useMe();
  const q = useQuery({ queryKey: ["venues"], queryFn: () => call(api.GET("/api/v1/venues")) });
  const manage = can(me, "exhibition.manage");
  const columns: Column<Schemas["VenueOut"]>[] = [
    { key: "name", header: "Name", cell: (v) => v.name },
    { key: "city", header: "City", cell: (v) => v.city ?? "" },
    { key: "country", header: "Country", hideBelow: "md", cell: (v) => countryName(v.country) },
  ];
  return (
    <Page>
      <PageHead title="Venues" actions={manage ? <Button asChild variant="primary"><Link to="/app/venues/new">Add Venue</Link></Button> : null} />
      <Panel>
        <ArrayBody query={q} empty={<EmptyState title="No venues yet." action={manage ? <Button asChild variant="primary"><Link to="/app/venues/new">Add Venue</Link></Button> : undefined} />}>
          {(rows) => <ListTable caption="Venues" rows={rows} columns={columns} rowKey={(v) => v.id} rowLink={manage ? (v) => ({ to: "/app/venues/$venueId", params: { venueId: v.id } }) : undefined} />}
        </ArrayBody>
      </Panel>
    </Page>
  );
}
