import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Metric } from "@/ui/metric";
import { Panel, PanelHeader } from "@/ui/page";
import { ErrorState, Skeleton } from "@/ui/states";

/** Overview: leads per stage and contract money of the edition, inside the user's lead scope. */
export function ExhibitorPipelinePanel({ editionId }: { editionId: string }) {
  const q = useQuery({
    queryKey: ["exhibitor-leads", editionId, "pipeline"],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/pipeline", { params: { query: { edition_id: editionId } } })),
    refetchInterval: 60_000,
  });
  return (
    <Panel>
      <PanelHeader
        title="How are exhibitor sales going?"
        actions={<Button asChild size="sm" variant="ghost"><Link to="/app/exhibitor-leads/board">Open Board</Link></Button>}
      />
      {q.isPending ? (
        <div className="p-5"><Skeleton className="h-28 w-full" /></div>
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : (
        <div className="flex flex-col gap-6 p-5">
          <div className="grid grid-cols-2 gap-5 md:grid-cols-5">
            {q.data.stages.map((s) => (
              <Link key={s.stage} to="/app/exhibitor-leads" search={{ stage: s.stage, page: 1, page_size: 20 }} className="rounded-[8px] hover:bg-subtle">
                <Metric label={label("sales_stage", s.stage)} value={s.count} />
              </Link>
            ))}
            <Metric label="Booths held" value={`${q.data.booths_held} / ${q.data.booths_for_sale}`} hint={`${q.data.draft_contracts} ${q.data.draft_contracts === 1 ? "contract" : "contracts"} waiting for signature`} />
          </div>
          {q.data.money.length === 0 ? (
            <p className="text-[13px] text-muted">No signed contracts yet. Money shows here once exhibitors sign.</p>
          ) : (
            q.data.money.map((m) => (
              <div key={m.currency} className="border-t border-line pt-5">
                <p className="mb-3 text-[12px] text-label">
                  {m.signed_contracts} signed {m.signed_contracts === 1 ? "contract" : "contracts"}, {m.paid_contracts} fully paid ({m.currency})
                </p>
                <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
                  <Metric label="Signed value" value={formatMoney(m.signed_value, m.currency)} />
                  <Metric label="Paid (verified)" value={formatMoney(m.verified_amount, m.currency)} />
                  <Metric label="Waiting for verification" value={formatMoney(m.pending_amount, m.currency)} />
                  <Metric label="Outstanding" value={formatMoney(m.outstanding_amount, m.currency)} />
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </Panel>
  );
}
