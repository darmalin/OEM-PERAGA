import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { gatesQuery } from "@/features/gate/queries";
import { ScanTable } from "@/features/gate/scan-table";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { DateFilter, FilterBar, SelectFilter } from "@/ui/filters";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";

const search = z.object({
  gate_id: z.string().optional(),
  local_date: z.string().optional(),
  result: z.string().optional(),
  mode: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(20),
});

export const Route = createFileRoute("/app/scans")({ validateSearch: search, component: Scans });

function Scans() {
  const me = useMe();
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (p: Partial<z.infer<typeof search>>) => void navigate({ search: (prev) => ({ ...prev, page: 1, ...p }), replace: true });
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const query = useQuery({
    queryKey: ["scans", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    refetchInterval: 15_000,
    queryFn: () => call(api.GET("/api/v1/gate/scans", { params: { query: { edition_id: edition!.id, ...s } as never } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const filtered = Boolean(s.gate_id || s.local_date || s.result || s.mode);
  return (
    <Page>
      <PageHead
        title="Scan History"
        meta={`Every scan, valid or not. Times in ${edition.timezone}. Refreshes every 15 seconds.`}
        actions={can(me, "gate.override") ? <Button asChild variant="primary"><Link to="/app/overrides/new">Manual Entry</Link></Button> : null}
      />
      <Panel>
        <FilterBar active={filtered} onClear={() => void navigate({ search: { page: 1, page_size: s.page_size } })}>
          <SelectFilter label="Gate" value={s.gate_id} onChange={(v) => set({ gate_id: v })} options={(gates.data ?? []).map((g) => ({ value: g.id, label: `${g.code} ${g.name}` }))} />
          <DateFilter label="Day" value={s.local_date} onChange={(v) => set({ local_date: v })} />
          <SelectFilter label="Result" value={s.result} onChange={(v) => set({ result: v })} options={options("scan_result")} />
          <SelectFilter label="Mode" value={s.mode} onChange={(v) => set({ mode: v })} options={options("scan_mode")} />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => set({ page })}
          onPageSize={(page_size) => set({ page_size })}
          empty={<EmptyState title={filtered ? "No scans match these filters." : "No scans yet. They appear here as soon as a gate device scans a QR code."} />}
        >
          {(items) => <ScanTable rows={items} gates={gates.data ?? []} timezone={edition.timezone} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
