import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";

import { formatDateTime } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { ListBody } from "@/ui/list";
import { Metric } from "@/ui/metric";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

/** Lead-scoped email jobs, with whole-history counts independent of pagination. */
export function LeadEmailTab({ leadId, timezone }: { leadId: string; timezone?: string }) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const query = useQuery({
    queryKey: ["lead-emails", leadId, page, pageSize],
    queryFn: () => call(api.GET("/api/v1/visitor-leads/{lead_id}/emails", {
      params: { path: { lead_id: leadId }, query: { page, page_size: pageSize } },
    })),
    refetchInterval: (q) => (q.state.data?.pending_count ? 10_000 : false),
  });
  if (query.isPending) return <FormSkeleton />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const history = query.data;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
        <div>
          <h2 className="text-[14px] font-semibold">Email History</h2>
          <p className="mt-1 text-[12px] text-label">Emails linked to this lead. Sent counts email messages, including resends, rather than delivery attempts.</p>
        </div>
        <Button onClick={() => void query.refetch()} loading={query.isFetching}><RefreshCw aria-hidden />Refresh</Button>
      </div>
      <div className="grid grid-cols-2 gap-4 border-b border-line bg-subtle p-5 sm:grid-cols-5">
        <Metric label="Sent" value={history.sent_count} />
        <Metric label="Pending" value={history.pending_count} />
        <Metric label="Failed" value={history.failed_count} />
        <Metric label="Cancelled" value={history.cancelled_count} />
        <Metric label="Total Emails" value={history.total} />
      </div>
      <ListBody query={query} onPage={setPage} onPageSize={(size) => { setPageSize(size); setPage(1); }}
        empty={<EmptyState title="No emails have been recorded for this lead yet." />}>
        {(emails) => (
          <ul className="divide-y divide-line" aria-label="Emails to this lead">
            {emails.map((email) => (
              <li key={email.id} className="px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-semibold break-words">{email.subject || label("email_kind", email.kind)}</p>
                    <p className="mt-1 text-[12px] text-label">{label("email_kind", email.kind)}</p>
                  </div>
                  <Indicator value={email.status} group="email_status" />
                </div>
                <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-[13px]">
                  <dt className="text-label">To</dt><dd className="break-all">{email.recipient}</dd>
                  {email.from_address ? <><dt className="text-label">From</dt><dd className="break-all">{email.from_address}</dd></> : null}
                  <dt className="text-label">Queued</dt><dd className="tabular">{formatDateTime(email.queued_at, timezone)}</dd>
                  {email.sent_at ? <><dt className="text-label">Sent</dt><dd className="tabular">{formatDateTime(email.sent_at, timezone)}</dd></> : null}
                  <dt className="text-label">Attempts</dt><dd className="tabular">{email.attempts}</dd>
                </dl>
                {email.error_summary ? <p className="mt-2 text-[13px] break-words text-required">{email.error_summary}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </ListBody>
    </div>
  );
}
