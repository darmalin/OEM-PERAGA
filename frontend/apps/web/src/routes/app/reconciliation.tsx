import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { gatesQuery } from "@/features/gate/queries";
import { ScanTable } from "@/features/gate/scan-table";
import { useEdition } from "@/lib/edition";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/reconciliation")({
  validateSearch: z.object({ page: z.number().int().min(1).default(1), page_size: z.number().int().default(20) }),
  component: Reconciliation,
});

function Reconciliation() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const query = useQuery({
    queryKey: ["reconciliation", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/gate/reconciliation", { params: { query: { edition_id: edition!.id, ...s } } })),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  return (
    <Page>
      <PageHead
        title="Reconciliation"
        meta="Offline scans where the server's final answer differs from what the device showed. The server's answer counts."
      />
      <Panel>
        <ListBody
          query={query}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => void navigate({ search: { page: 1, page_size } })}
          empty={<EmptyState title="Nothing to reconcile. Every offline scan matched what the device showed." />}
        >
          {(items) => <ScanTable rows={items} gates={gates.data ?? []} timezone={edition.timezone} showProvisional />}
        </ListBody>
      </Panel>
    </Page>
  );
}
