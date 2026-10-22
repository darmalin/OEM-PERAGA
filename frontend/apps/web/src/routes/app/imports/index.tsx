import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { formatBytes, formatDateTime, formatNumber } from "@/lib/format";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/imports/")({
  validateSearch: z.object({ page: z.number().int().min(1).default(1), page_size: z.number().int().default(20) }),
  component: Imports,
});

function Imports() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const query = useQuery({
    queryKey: ["imports", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/visitor-leads/imports", { params: { query: { edition_id: edition!.id, ...s } } })),
    refetchInterval: (q) => (q.state.data?.items.some((j) => j.status === "QUEUED" || j.status === "RUNNING") ? 3000 : false),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const columns: Column<Schemas["ImportJobOut"]>[] = [
    { key: "file", header: "File", cell: (j) => j.file_name },
    { key: "status", header: "Status", cell: (j) => <Indicator value={j.status} group="job_status" /> },
    { key: "rows", header: "Created / Duplicate / Invalid", hideBelow: "md", cell: (j) => <span className="tabular">{formatNumber(j.created_count)} / {formatNumber(j.duplicate_count)} / {formatNumber(j.invalid_count)}</span> },
    { key: "size", header: "Size", hideBelow: "lg", cell: (j) => <span className="text-label tabular">{formatBytes(j.file_size)}</span> },
    { key: "at", header: "Uploaded", hideBelow: "lg", cell: (j) => <span className="text-label tabular">{formatDateTime(j.created_at, edition.timezone)}</span> },
  ];
  return (
    <Page>
      <PageHead edition title="Imports" meta="Excel files of visitor leads. Each row is checked on its own; one bad row never stops the file." actions={<Button asChild variant="primary"><Link to="/app/imports/new">Import Excel</Link></Button>} />
      <Panel>
        <ListBody
          query={query}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => void navigate({ search: { page: 1, page_size } })}
          empty={<EmptyState title="No imports yet. Download the template, fill it, and upload it." action={<Button asChild variant="primary"><Link to="/app/imports/new">Import Excel</Link></Button>} />}
        >
          {(items) => <ListTable caption="Import jobs" rows={items} columns={columns} rowKey={(j) => j.id} rowLink={(j) => ({ to: "/app/imports/$jobId", params: { jobId: j.id } })} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
