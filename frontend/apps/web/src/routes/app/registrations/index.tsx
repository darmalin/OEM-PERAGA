import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { formatDateTime } from "@/lib/format";
import { label, options } from "@/lib/labels";
import { FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const search = z.object({
  q: z.string().optional(),
  channel: z.string().optional(),
  qr_status: z.string().optional(),
  email_status: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});

export const Route = createFileRoute("/app/registrations/")({ validateSearch: search, component: Registrations });

function Registrations() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<z.infer<typeof search>>) => void navigate({ search: (p) => ({ ...p, page: 1, ...patch }), replace: true });
  const query = useQuery({
    queryKey: ["registrations", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(api.GET("/api/v1/visitor-registrations", { params: { query: { edition_id: edition!.id, ...s } as never } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const filtered = Boolean(s.q || s.channel || s.qr_status || s.email_status);
  const columns: Column<Schemas["RegistrationOut"]>[] = [
    { key: "name", header: "Visitor", cell: (r) => r.first_name },
    { key: "code", header: "Registration ID", cell: (r) => <span className="tabular text-muted">{r.registration_code}</span> },
    { key: "channel", header: "Channel", hideBelow: "lg", cell: (r) => label("channel", r.channel) },
    { key: "qr", header: "QR", cell: (r) => <Indicator value={r.qr_status} group="qr_status" /> },
    { key: "email", header: "QR Email", hideBelow: "md", cell: (r) => (r.email_status ? <Indicator value={r.email_status} group="email_status" /> : <span className="text-label">Not sent</span>) },
    { key: "at", header: "Registered", hideBelow: "lg", cell: (r) => <span className="text-label tabular">{formatDateTime(r.registered_at, edition.timezone)}</span> },
  ];
  return (
    <Page>
      <PageHead title="Registrations" meta={query.data ? `${query.data.total.toLocaleString("en")} in ${edition.code}` : edition.code} />
      <Panel>
        <FilterBar active={filtered} onClear={() => void navigate({ search: { page: 1, page_size: s.page_size } })}>
          <SearchFilter value={s.q} onChange={(q) => set({ q })} placeholder="Name or Registration ID" label="Search registrations" />
          <SelectFilter label="Channel" value={s.channel} onChange={(v) => set({ channel: v })} options={options("channel")} />
          <SelectFilter label="QR" value={s.qr_status} onChange={(v) => set({ qr_status: v })} options={options("qr_status").filter((o) => o.value !== "NONE")} />
          <SelectFilter label="QR Email" value={s.email_status} onChange={(v) => set({ email_status: v })} options={options("email_status")} />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => set({ page })}
          onPageSize={(page_size) => set({ page_size })}
          empty={<EmptyState title={filtered ? "No registrations match these filters." : "No visitors are registered yet. Register a visitor from their lead page."} />}
        >
          {(items) => <ListTable caption="Registrations" rows={items} columns={columns} rowKey={(r) => r.id} rowLink={(r) => ({ to: "/app/registrations/$registrationId", params: { registrationId: r.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
