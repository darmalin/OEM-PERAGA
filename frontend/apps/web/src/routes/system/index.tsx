import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { formatDateTime } from "@/lib/format";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, TableSkeleton } from "@/ui/states";

export const Route = createFileRoute("/system/")({ component: Health });

function Health() {
  const q = useQuery({
    queryKey: ["health"],
    queryFn: () => call(api.GET("/api/v1/health/ready")),
    refetchInterval: 15_000,
  });
  return (
    <Page>
      <PageHead
        title="System Health"
        meta={q.dataUpdatedAt ? `Checked ${formatDateTime(new Date(q.dataUpdatedAt).toISOString())}, every 15 seconds` : "Checking"}
        actions={<Button onClick={() => void q.refetch()} loading={q.isFetching}>Check Now</Button>}
      />
      <Panel>
        {q.isPending ? (
          <TableSkeleton rows={3} />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => void q.refetch()} />
        ) : (
          <ul className="divide-y divide-line">
            <li className="flex items-center justify-between px-5 py-3 text-[14px]">
              <span className="font-medium">API</span>
              <Indicator value={q.data.status === "ok" ? "ACTIVE" : "FAILED"} text={q.data.status === "ok" ? "Ready" : q.data.status} />
            </li>
            {Object.entries(q.data.checks).map(([name, status]) => (
              <li key={name} className="flex items-center justify-between px-5 py-3 text-[14px]">
                <span className="capitalize">{name}</span>
                <Indicator value={status === "ok" ? "ACTIVE" : "FAILED"} text={status === "ok" ? "Reachable" : String(status)} />
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </Page>
  );
}
