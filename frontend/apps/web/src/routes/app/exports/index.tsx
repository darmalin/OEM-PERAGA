import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { formatBytes, formatDateTime, formatNumber } from "@/lib/format";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/exports/")({
  validateSearch: z.object({ page: z.number().int().min(1).default(1), page_size: z.number().int().default(20) }),
  component: Exports,
});

async function download(id: string) {
  try {
    // Ask for a fresh signed link each time; links expire after a few minutes.
    const job = await call(api.GET("/api/v1/exports/{job_id}", { params: { path: { job_id: id } } }));
    if (job.download_url) window.location.assign(job.download_url);
  } catch (e) {
    notifyError(e);
  }
}

function Exports() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const query = useQuery({
    queryKey: ["exports", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/exports", { params: { query: { edition_id: edition!.id, ...s } } })),
    refetchInterval: (q) => (q.state.data?.items.some((j) => j.status === "QUEUED" || j.status === "RUNNING") ? 2500 : false),
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const columns: Column<Schemas["ExportJobOut"]>[] = [
    { key: "what", header: "Export", cell: (j) => j.file_name ?? (j.kind === "VISITORS" ? "Visitor leads" : "Report") },
    { key: "status", header: "Status", cell: (j) => <Indicator value={j.status} group="job_status" /> },
    { key: "rows", header: "Rows", hideBelow: "md", cell: (j) => <span className="tabular">{j.row_count != null ? formatNumber(j.row_count) : ""}</span> },
    { key: "size", header: "Size", hideBelow: "lg", cell: (j) => <span className="text-label tabular">{formatBytes(j.file_size)}</span> },
    { key: "expires", header: "Available until", hideBelow: "lg", cell: (j) => <span className="text-label tabular">{j.status === "COMPLETED" ? formatDateTime(j.expires_at, edition.timezone) : ""}</span> },
    { key: "dl", header: "", className: "text-right", cell: (j) => (j.status === "COMPLETED" ? <Button size="sm" onClick={() => void download(j.id)}><Download aria-hidden />Download</Button> : j.error_summary ? <span className="text-[var(--red-fg)]">{j.error_summary}</span> : null) },
  ];
  return (
    <Page>
      <PageHead title="Exports" meta="Files are built in the background and kept for 24 hours. Every export is audited." actions={<Button asChild variant="primary"><Link to="/app/exports/new">New Export</Link></Button>} />
      <Panel>
        <ListBody
          query={query}
          onPage={(page) => void navigate({ search: (p) => ({ ...p, page }) })}
          onPageSize={(page_size) => void navigate({ search: { page: 1, page_size } })}
          empty={<EmptyState title="No exports yet." action={<Button asChild variant="primary"><Link to="/app/exports/new">New Export</Link></Button>} />}
        >
          {(items) => <ListTable caption="Exports" rows={items} columns={columns} rowKey={(j) => j.id} />}
        </ListBody>
      </Panel>
    </Page>
  );
}
