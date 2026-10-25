import { api, call } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { useState } from "react";

import { useEdition } from "@/lib/edition";
import { formatDateTime, formatNumber } from "@/lib/format";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Metric } from "@/ui/metric";
import { Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/imports/$jobId")({ component: ImportJob });

function ImportJob() {
  const { jobId } = Route.useParams();
  const { edition } = useEdition();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const job = useQuery({
    queryKey: ["import", jobId],
    queryFn: () => call(api.GET("/api/v1/visitor-leads/imports/{job_id}", { params: { path: { job_id: jobId } } })),
    refetchInterval: (q) => (q.state.data && ["QUEUED", "RUNNING"].includes(q.state.data.status) ? 2000 : false),
  });
  const finished = job.data && !["QUEUED", "RUNNING"].includes(job.data.status);
  const errors = useQuery({
    queryKey: ["import-errors", jobId, page, pageSize],
    enabled: Boolean(finished),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/visitor-leads/imports/{job_id}/errors", { params: { path: { job_id: jobId }, query: { page, page_size: pageSize } } })),
  });

  const downloadErrors = async () => {
    try {
      const { url } = await call(api.GET("/api/v1/visitor-leads/imports/{job_id}/errors.xlsx", { params: { path: { job_id: jobId } } }));
      window.location.assign(url);
    } catch (e) {
      notifyError(e);
    }
  };

  if (job.isPending) return <Page><PageHead title="Import" back={{ to: "/app/imports", label: "Imports" }} /><Panel><FormSkeleton /></Panel></Page>;
  if (job.isError) return <Page><PageHead title="Import" back={{ to: "/app/imports", label: "Imports" }} /><Panel><ErrorState error={job.error} /></Panel></Page>;
  const j = job.data;
  const progress = j.total_rows ? Math.min(100, Math.round((j.processed_count / j.total_rows) * 100)) : null;

  return (
    <Page>
      <PageHead
        back={{ to: "/app/imports", label: "Imports" }}
        title={j.file_name}
        meta={<span className="tabular">Uploaded {formatDateTime(j.created_at, edition?.timezone)}{j.finished_at ? ` · finished ${formatDateTime(j.finished_at, edition?.timezone)}` : ""}</span>}
        indicators={<Indicator value={j.status} group="job_status" />}
        actions={
          <>
            {j.has_error_report ? <Button onClick={() => void downloadErrors()}><Download aria-hidden />Download Error Report</Button> : null}
            <Button asChild variant="primary"><Link to="/app/visitor-leads">Open Visitor Leads</Link></Button>
          </>
        }
      />
      <Panel>
        <div className="grid grid-cols-2 gap-6 p-5 md:grid-cols-4">
          <Metric label="Rows processed" value={j.processed_count} hint={j.total_rows ? `of ${formatNumber(j.total_rows)}` : undefined} />
          <Metric label="Leads created" value={j.created_count} />
          <Metric label="Duplicates" value={j.duplicate_count} hint="Same email or phone in this edition" />
          <Metric label="Invalid rows" value={j.invalid_count} />
        </div>
        {progress != null && !finished ? (
          <div className="px-5 pb-5" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100} aria-label="Import progress">
            <div className="h-2 rounded-full bg-input"><div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${progress}%` }} /></div>
          </div>
        ) : null}
        {j.auto_assign ? (
          <div className="border-t border-line px-5 py-4 text-[13px]">
            <p className="font-medium">
              <span className="tabular">{formatNumber(j.assigned_count)}</span> new {j.assigned_count === 1 ? "lead" : "leads"} shared among the edition's sales teams
              {!finished && j.assigned_count === 0 ? <span className="font-normal text-label"> · after the rows are read</span> : null}
            </p>
            {j.assigned_to?.length ? (
              <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-muted" aria-label="Leads per person">
                {j.assigned_to.map((a) => (
                  <li key={a.user_id}>{a.full_name} <span className="tabular text-ink">{formatNumber(a.count)}</span></li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
        {j.error_summary ? <p role="alert" className="mx-5 mb-5 rounded-[8px] bg-[var(--red-bg)] px-3 py-2 text-[13px] text-[var(--red-fg)]">{j.error_summary}</p> : null}
      </Panel>
      {finished ? (
        <Panel className="mt-6">
          <PanelHeader title="Rows that were not imported" />
          <ListBody
            query={errors}
            onPage={setPage}
            onPageSize={(n) => { setPageSize(n); setPage(1); }}
            empty={<EmptyState title="Every row was imported." />}
          >
            {(items) => (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <caption className="sr-only">Rows not imported</caption>
                  <thead>
                    <tr className="border-b border-line text-left text-[12px] text-label">
                      <th scope="col" className="px-4 py-2.5 font-normal">Row</th>
                      <th scope="col" className="px-4 py-2.5 font-normal">Reason</th>
                      <th scope="col" className="px-4 py-2.5 font-normal">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((e) => (
                      <tr key={e.row_number} className="border-b border-line last:border-b-0">
                        <td className="px-4 py-2 tabular">{e.row_number}</td>
                        <td className="px-4 py-2"><Indicator value={e.reason_code.startsWith("DUPLICATE") ? "PENDING" : "FAILED"} text={e.reason_code.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())} /></td>
                        <td className="px-4 py-2 text-muted">{e.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ListBody>
        </Panel>
      ) : null}
    </Page>
  );
}
