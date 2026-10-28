import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { RefreshCw } from "lucide-react";
import { z } from "zod";

import { dashboardQuery, type DashboardSearch } from "@/features/dashboard/api";
import { MetricCards } from "@/features/dashboard/cards";
import { EmailReport } from "@/features/dashboard/email-report";
import { ReferenceOverview } from "@/features/dashboard/overview";
import { DashboardOverviewFilters } from "@/features/dashboard/overview-filters";
import { DashboardFilters } from "@/features/dashboard/filters";
import { dayLabel, daysBetween, emptyRow } from "@/features/dashboard/metrics";
import { RecapTable } from "@/features/dashboard/recap-table";
import { Button } from "@/ui/button";
import { Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, Skeleton } from "@/ui/states";
import { TabList, TabPanel, Tabs } from "@/ui/tabs";

const TABS = ["dashboard", "today", "daily", "edition", "source", "user", "email"] as const;
type Tab = (typeof TABS)[number];

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const today = () => iso(new Date());
const monthAgo = () => iso(new Date(Date.now() - 29 * 864e5));

const search = z.object({
  tab: z.enum(TABS).default("dashboard"),
  from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).default(monthAgo),
  to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).default(today),
  edition: z.string().optional(),
  country: z.string().optional(),
  user: z.string().optional(),
  team: z.string().optional(),
  source: z.string().optional(),
  status: z.string().optional(),
  quality: z.string().optional(),
  buyer: z.string().optional(),
  attend: z.string().optional(),
  b2b: z.enum(["yes", "no"]).optional(),
});

export const Route = createFileRoute("/app/dashboard")({ validateSearch: search, component: Dashboard });

function Dashboard() {
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<DashboardSearch & { tab: Tab }>) => void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });
  const filters: DashboardSearch = s;
  const range = s.from <= s.to ? s : { ...s, to: s.from };
  return (
    <Page className="max-w-none">
      <PageHead
        title="Dashboard"
        meta={`Calls, verification, and leads from ${dayLabel(range.from)} to ${dayLabel(range.to)}. Updates every minute.`}
        actions={<RefreshButton />}
      />
      <Panel>
        <Tabs value={s.tab} onValueChange={(v) => set({ tab: v as Tab })}>
          <TabList
            className="dashboard-tabs"
            tabs={[
              { value: "dashboard", label: "Dashboard" },
              { value: "today", label: "Today" },
              { value: "daily", label: "Daily Comparison" },
              { value: "edition", label: "Recap By Exhibition Type" },
              { value: "source", label: "Recap By Source" },
              { value: "user", label: "Recap By User" },
              { value: "email", label: "Email Report" },
            ]}
          />
          {s.tab === "dashboard" ? <DashboardOverviewFilters s={filters} set={set} onClear={() => void navigate({ search: { tab: s.tab, from: s.from, to: s.to }, replace: true })} /> : (
          <DashboardFilters
            s={filters}
            set={set}
            showDates={s.tab !== "today"}
            emailOnly={s.tab === "email"}
            onClear={() => void navigate({ search: { tab: s.tab, from: s.from, to: s.to }, replace: true })}
          />
          )}
          <div className="bg-subtle p-4">
            <TabPanel value="dashboard"><ReferenceOverview s={range} /></TabPanel>
            <TabPanel value="today"><TodayTab s={range} /></TabPanel>
            <TabPanel value="daily"><Recap s={range} group="day" title="Daily Comparison" /></TabPanel>
            <TabPanel value="edition"><Recap s={range} group="day_edition" title="Recap By Exhibition Type" keyHeader="Exhibition Type" /></TabPanel>
            <TabPanel value="source"><Recap s={range} group="day_source" title="Recap By Source" keyHeader="Source" /></TabPanel>
            <TabPanel value="user"><Recap s={range} group="day_user" title="Recap By User" keyHeader="User" /></TabPanel>
            <TabPanel value="email"><EmailReport s={range} /></TabPanel>
          </div>
        </Tabs>
      </Panel>
    </Page>
  );
}

function RefreshButton() {
  const queryClient = useQueryClient();
  const busy = useIsFetching({ queryKey: ["dashboard"] }) > 0;
  return (
    <Button onClick={() => void queryClient.invalidateQueries({ queryKey: ["dashboard"] })} loading={busy}>
      <RefreshCw aria-hidden />Refresh
    </Button>
  );
}

const period = (s: DashboardSearch) => (s.from === s.to ? dayLabel(s.from) : `${dayLabel(s.from)} to ${dayLabel(s.to)}`);

function TodayTab({ s }: { s: DashboardSearch }) {
  const day = today();
  const q = useQuery(dashboardQuery(s, "total", { from: day, to: day }));
  if (q.isPending) return <Skeleton className="h-[180px]" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return <MetricCards row={q.data.rows[0] ?? emptyRow()} period={`Today, ${dayLabel(day)}`} />;
}

function Recap({ s, group, title, keyHeader }: { s: DashboardSearch; group: "day" | "day_edition" | "day_source" | "day_user"; title: string; keyHeader?: string }) {
  const q = useQuery(dashboardQuery(s, group));
  if (q.isPending) return <Skeleton className="h-[400px]" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return (
    <RecapTable
      title={`${title} · ${period(s)}`}
      days={daysBetween(s.from, s.to)}
      rows={q.data.rows}
      keys={group === "day" ? undefined : q.data.keys}
      keyHeader={keyHeader}
      userColumns={group === "day_user"}
      fileName={`${title.toLowerCase().replaceAll(" ", "-")}-${s.from}-${s.to}`}
    />
  );
}
