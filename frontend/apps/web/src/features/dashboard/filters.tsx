import { useQuery } from "@tanstack/react-query";

import { leadSourcesQuery } from "@/features/leads/queries";
import { countryName } from "@/lib/countries";
import { useEdition } from "@/lib/edition";
import { options } from "@/lib/labels";
import { DateFilter, FilterBar, SelectFilter } from "@/ui/filters";

import { dashboardOptionsQuery, type DashboardSearch } from "./api";

/** One row of filters shared by every tab (the old system's filter bar). */
export function DashboardFilters({ s, set, onClear, showDates = true }: {
  s: DashboardSearch;
  set: (patch: Partial<DashboardSearch>) => void;
  onClear: () => void;
  showDates?: boolean;
}) {
  const { editions } = useEdition();
  const opts = useQuery(dashboardOptionsQuery);
  const sources = useQuery(leadSourcesQuery(true));
  const active = Boolean(s.edition || s.country || s.user || s.team || s.source || s.status || s.quality || s.buyer || s.attend || s.b2b);
  return (
    <FilterBar active={active} onClear={onClear}>
      {showDates ? (
        <>
          <DateFilter label="From" value={s.from} onChange={(v) => v && set({ from: v })} />
          <DateFilter label="To" value={s.to} onChange={(v) => v && set({ to: v })} />
        </>
      ) : null}
      <SelectFilter label="Country" value={s.country} onChange={(v) => set({ country: v })} options={(opts.data?.countries ?? []).map((c) => ({ value: c, label: countryName(c) ?? c }))} />
      <SelectFilter label="User" value={s.user} onChange={(v) => set({ user: v })} options={(opts.data?.users ?? []).map((u) => ({ value: u.id, label: u.label }))} />
      <SelectFilter label="Team" value={s.team} onChange={(v) => set({ team: v })} options={(opts.data?.teams ?? []).map((t) => ({ value: t.id, label: t.label }))} />
      <SelectFilter label="Exhibition Type" value={s.edition} onChange={(v) => set({ edition: v })} options={editions.map((e) => ({ value: e.id, label: e.code }))} />
      <SelectFilter label="Source" value={s.source} onChange={(v) => set({ source: v })} options={(sources.data ?? []).map((o) => ({ value: o.id, label: o.name }))} />
      <SelectFilter label="Status" value={s.status} onChange={(v) => set({ status: v })} options={options("telemarketing_status")} />
      <SelectFilter label="Lead Quality" value={s.quality} onChange={(v) => set({ quality: v })} options={options("validity")} />
      <SelectFilter label="Buyer Type" value={s.buyer} onChange={(v) => set({ buyer: v })} options={options("buyer_type")} />
      <SelectFilter label="Attend" value={s.attend} onChange={(v) => set({ attend: v })} options={options("attend")} />
      <SelectFilter label="B2B Matching" value={s.b2b} onChange={(v) => set({ b2b: v as DashboardSearch["b2b"] })} options={[{ value: "yes", label: "Yes" }, { value: "no", label: "No" }]} />
    </FilterBar>
  );
}
