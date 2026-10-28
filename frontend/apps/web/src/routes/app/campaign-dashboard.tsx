import { api, call, type Schemas } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Megaphone } from "lucide-react";
import { z } from "zod";

import { campaignLinksQuery } from "@/features/campaigns/queries";
import { Breakdown } from "@/features/dashboard/cards";
import { daysBetween } from "@/features/dashboard/metrics";
import { LineChart } from "@/features/dashboard/trend-chart";
import { useEdition } from "@/lib/edition";
import { formatNumber } from "@/lib/format";
import { Button } from "@/ui/button";
import { DateFilter, FilterBar, SelectFilter } from "@/ui/filters";
import { Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, TableSkeleton } from "@/ui/states";

type Dashboard = Schemas["CampaignDashboardOut"];

const search = z.object({
  campaign: z.string().optional(),
  from: z.string().optional(),
  to: z.string().optional(),
});

export const Route = createFileRoute("/app/campaign-dashboard")({ validateSearch: search, component: CampaignDashboard });

const pct = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 1000) / 10}%` : "–");

function CampaignDashboard() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<z.infer<typeof search>>) => void navigate({ search: (prev) => ({ ...prev, ...patch }), replace: true });
  const links = useQuery({ ...campaignLinksQuery(edition?.id), enabled: Boolean(edition) });
  const q = useQuery({
    queryKey: ["campaign-dashboard", edition?.id, s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET("/api/v1/reports/campaigns", {
          params: { query: { edition_id: edition!.id, campaign_link_id: s.campaign, date_from: s.from, date_to: s.to } },
        }),
      ),
  });

  if (!edition) return <Page><EmptyState title="Choose an Exhibition Type." /></Page>;
  const filtered = Boolean(s.campaign || s.from || s.to);

  return (
    <Page>
      <PageHead
        edition
        title="Form Dashboard"
        meta={`How ${edition.code}'s campaign links perform, from form opens to visitors at the gate. Days in ${edition.timezone}.`}
        actions={
          <Button asChild>
            <Link to="/app/campaigns"><Megaphone aria-hidden />Form</Link>
          </Button>
        }
      />
      <Panel className="mb-6">
        <FilterBar active={filtered} onClear={() => void navigate({ search: {}, replace: true })}>
          <SelectFilter label="Campaign" allLabel="All campaigns" value={s.campaign} onChange={(campaign) => set({ campaign })} options={(links.data ?? []).map((l) => ({ value: l.id, label: l.name }))} />
          <DateFilter label="From" value={s.from} onChange={(from) => set({ from })} />
          <DateFilter label="To" value={s.to} onChange={(to) => set({ to })} />
        </FilterBar>
      </Panel>
      {q.isPending ? (
        <Panel><TableSkeleton rows={4} /></Panel>
      ) : q.isError ? (
        <Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel>
      ) : (
        <DashboardBody d={q.data} period={s.from || s.to ? `${s.from ?? "start"} to ${s.to ?? "today"}` : "All time"} />
      )}
    </Page>
  );
}

function DashboardBody({ d, period }: { d: Dashboard; period: string }) {
  const t = d.totals;
  const tiles: { label: string; value: string; note: string }[] = [
    { label: "Form Opens", value: formatNumber(t.views), note: "One per visitor per day" },
    { label: "Registrations", value: formatNumber(t.registrations), note: period },
    { label: "Conversion", value: t.conversion == null ? "–" : `${Math.round(t.conversion * 1000) / 10}%`, note: "Registrations ÷ opens; over 100% when one device registers several people" },
    { label: "Already Registered", value: formatNumber(t.duplicates), note: "Same email or phone again" },
    { label: "Blocked as Bots", value: formatNumber(t.bots), note: "Not saved" },
  ];
  const days = d.days.length ? daysBetween(d.days[0]!.day, d.days[d.days.length - 1]!.day) : [];
  const byDay = new Map(d.days.map((x) => [x.day, x]));
  const f = d.funnel;
  const steps: { label: string; value: number }[] = [
    { label: "Registered", value: f.registered },
    { label: "Called", value: f.called },
    { label: "Answered", value: f.answered },
    { label: "Valid lead", value: f.valid },
    { label: "Plans to attend", value: f.attend },
    { label: "Checked in at the gate", value: f.checked_in },
  ];
  const utm = (rows: Schemas["Count"][]) => rows.map((r) => ({ key: r.key ?? "none", label: r.key ?? "(not set)", value: r.count }));

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {tiles.map((x) => (
          <div key={x.label} className="min-w-0 rounded-[10px] border border-line bg-bg px-4 py-3">
            <p className="truncate text-[12px] text-label">{x.label}</p>
            <p className="mt-0.5 text-[22px] leading-7 font-semibold tracking-[-0.01em] tabular">{x.value}</p>
            <p className="line-clamp-2 text-[12px] text-label">{x.note}</p>
          </div>
        ))}
      </div>

      <Panel>
        <PanelHeader title="Per day" />
        <div className="p-5 max-md:px-4">
          {days.length ? (
            <LineChart
              days={days}
              what="Form opens and registrations per day"
              series={[
                { key: "views", label: "Form opens", color: "var(--series-1)" },
                { key: "registrations", label: "Registrations", color: "var(--series-2)" },
              ]}
              value={(day, key) => (byDay.get(day)?.[key as "views" | "registrations"] ?? 0)}
            />
          ) : (
            <p className="text-[13px] text-label">No form opens or registrations in this period.</p>
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="From registration to the gate" />
          <ol className="flex flex-col gap-3 p-5 text-[13px] max-md:px-4" aria-label="Funnel">
            {steps.map((st) => (
              <li key={st.label} className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-1">
                <span className="truncate">{st.label}</span>
                <span className="font-medium tabular">{formatNumber(st.value)}</span>
                <span className="w-14 text-right text-[12px] text-label tabular">{pct(st.value, f.registered)}</span>
                <span className="col-span-3 h-2 rounded-full bg-input" aria-hidden>
                  <span className="block h-full rounded-full bg-[var(--series-1)]" style={{ width: `${f.registered ? (st.value / f.registered) * 100 : 0}%` }} />
                </span>
              </li>
            ))}
          </ol>
          <p className="border-t border-line px-5 py-3 text-[12px] text-label max-md:px-4">
            Campaign leads you can see, registered in this period. Percentages are of registered.
          </p>
        </Panel>
        <div className="grid grid-cols-1 gap-6">
          <Breakdown title="UTM Source" values={utm(d.utm_source)} />
          <Breakdown title="UTM Medium" values={utm(d.utm_medium)} />
          <Breakdown title="UTM Campaign" values={utm(d.utm_campaign)} />
        </div>
      </div>

      <Panel>
        <PanelHeader title="Campaigns compared" />
        {d.campaigns.length === 0 ? (
          <EmptyState title="No campaign links in this edition." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <caption className="sr-only">Campaigns compared</caption>
              <thead>
                <tr className="border-b border-line text-left text-[12px] text-label">
                  <th scope="col" className="px-5 py-2.5 font-normal">Campaign</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-normal">Opens</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-normal">Registrations</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-normal">Conversion</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-normal">Valid</th>
                  <th scope="col" className="px-5 py-2.5 text-right font-normal">Checked in</th>
                </tr>
              </thead>
              <tbody>
                {d.campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-line last:border-b-0">
                    <th scope="row" className="px-5 py-2.5 text-left font-medium">{c.name}</th>
                    <td className="px-4 py-2.5 text-right tabular">{formatNumber(c.views)}</td>
                    <td className="px-4 py-2.5 text-right tabular">{formatNumber(c.registrations)}</td>
                    <td className="px-4 py-2.5 text-right tabular text-muted">{pct(c.registrations, c.views)}</td>
                    <td className="px-4 py-2.5 text-right tabular">{formatNumber(c.valid)}</td>
                    <td className="px-5 py-2.5 text-right tabular">{formatNumber(c.checked_in)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
