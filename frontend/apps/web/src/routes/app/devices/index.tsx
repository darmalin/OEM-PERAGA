import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { gatesQuery } from "@/features/gate/queries";
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

export const Route = createFileRoute("/app/devices/")({
  validateSearch: z.object({
    gate_id: z.string().optional(),
    status: z.string().optional(),
    page: z.number().int().min(1).default(1),
    page_size: z.number().int().default(20),
  }),
  component: Devices,
});

function Devices() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const query = useQuery({
    queryKey: ["devices", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/gate/devices", { params: { query: { edition_id: edition!.id, ...s } as never } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const gateName = (id: string) => gates.data?.find((g) => g.id === id)?.code ?? "";
  const columns: Column<Schemas["DeviceOut"]>[] = [
    { key: "name", header: "Device", cell: (d) => d.name },
    { key: "gate", header: "Gate", cell: (d) => <span className="tabular">{gateName(d.gate_id)}</span> },
    { key: "status", header: "Status", cell: (d) => <Indicator value={d.status} group="device_status" /> },
    { key: "seen", header: "Last seen", hideBelow: "md", cell: (d) => <span className="text-label">{d.last_seen_at ? relative(d.last_seen_at) : "Never"}</span> },
  ];
  return (
    <Page>
      <PageHead edition title="Scanner Devices" meta="Phones or tablets that scan QR codes at a gate. Revoke a device that is lost." actions={<Button asChild variant="primary"><Link to="/app/devices/new">Register Device</Link></Button>} />
      <Panel>
        <FilterBar>
          <SelectFilter label="Gate" value={s.gate_id} onChange={(v) => void navigate({ search: (p) => ({ ...p, gate_id: v, page: 1 }) })} options={(gates.data ?? []).map((g) => ({ value: g.id, label: `${g.code} ${g.name}` }))} />
          <SelectFilter label="Status" value={s.status} onChange={(v) => void navigate({ search: (p) => ({ ...p, status: v, page: 1 }) })} options={options("device_status")} />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => void navigate({ search: (p) => ({ ...p, page_size, page: 1 }) })}
          empty={<EmptyState title="No devices registered. Register one, then enter its activation code on the phone." action={<Button asChild variant="primary"><Link to="/app/devices/new">Register Device</Link></Button>} />}
        >
          {(items) => <ListTable caption="Scanner devices" rows={items} columns={columns} rowKey={(d) => d.id} rowLink={(d) => ({ to: "/app/devices/$deviceId", params: { deviceId: d.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
