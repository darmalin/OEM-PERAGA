import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { leadSourcesQuery } from "@/features/leads/queries";
import { countryName } from "@/lib/countries";
import { useEdition } from "@/lib/edition";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Input, Select } from "@/ui/input";

import { dashboardOptionsQuery, type DashboardSearch } from "./api";

const clear = { edition: undefined, country: undefined, user: undefined, team: undefined, source: undefined, status: undefined, quality: undefined, buyer: undefined, attend: undefined, b2b: undefined };
export function DashboardOverviewFilters({ s, set, onClear }: { s: DashboardSearch; set: (patch: Partial<DashboardSearch>) => void; onClear: () => void }) {
  const { editions } = useEdition();
  const opts = useQuery(dashboardOptionsQuery);
  const sources = useQuery(leadSourcesQuery(true));
  const [draft, setDraft] = useState<DashboardSearch>({ ...clear, ...s });
  const id = useId();
  const signature = JSON.stringify(s);
  const [applied, setApplied] = useState(signature);
  if (applied !== signature) { setApplied(signature); setDraft({ ...clear, ...s }); }
  const update = (key: keyof DashboardSearch, value: string) => setDraft(prev => ({ ...prev, [key]: value || undefined }));
  const fields: { key: keyof DashboardSearch; label: string; all: string; choices: { value: string; label: string }[] }[] = [
    { key: "user", label: "User", all: "All User", choices: (opts.data?.users ?? []).map(u => ({ value: u.id, label: u.label })) },
    { key: "edition", label: "Exhibition Type", all: "All Exhibition Type", choices: editions.map(e => ({ value: e.id, label: e.code })) },
    { key: "source", label: "Source", all: "All Source", choices: (sources.data ?? []).map(o => ({ value: o.id, label: o.name })) },
    { key: "status", label: "Status", all: "All Status", choices: options("telemarketing_status") },
    { key: "quality", label: "Lead Quality", all: "All Valid Lead", choices: options("validity") },
    { key: "buyer", label: "Buyer Type", all: "All Buyer Type", choices: options("buyer_type") },
    { key: "attend", label: "Attend", all: "All Attend", choices: options("attend") },
    { key: "b2b", label: "B2B Matching", all: "All B2B Matching", choices: [{ value: "yes", label: "Yes" }, { value: "no", label: "No" }] },
  ];
  return <form className="dashboard-reference border-b border-line bg-bg" aria-label="Dashboard filters" onSubmit={e => { e.preventDefault(); set(draft); }}>
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3 border-b border-line px-5 py-3">
      <label htmlFor={`${id}-from`} className="flex items-center gap-2 text-[12px] text-muted">From<Input id={`${id}-from`} className="w-[148px] bg-bg" type="date" required value={draft.from} max={draft.to} onChange={e => update("from", e.target.value)} /></label>
      <label htmlFor={`${id}-to`} className="flex items-center gap-2 text-[12px] text-muted">To<Input id={`${id}-to`} className="w-[148px] bg-bg" type="date" required value={draft.to} min={draft.from} onChange={e => update("to", e.target.value)} /></label>
      <Select aria-label="Country" className="dash-filter-select ml-auto w-[150px] max-md:ml-0" value={draft.country ?? ""} onChange={e => update("country", e.target.value)}><option value="">All Country</option>{(opts.data?.countries ?? []).map(c => <option key={c} value={c}>{countryName(c) ?? c}</option>)}</Select>
      <Select aria-label="Team" className="dash-filter-select w-[150px]" value={draft.team ?? ""} onChange={e => update("team", e.target.value)}><option value="">All Team</option>{(opts.data?.teams ?? []).map(t => <option key={t.id} value={t.id}>{t.label}</option>)}</Select>
    </div>
    <div className="dash-filter-grid px-5 py-3">
      {fields.map(f => <Select key={f.key} className="dash-filter-select w-full min-w-0" aria-label={f.label} value={draft[f.key] ?? ""} onChange={e => update(f.key, e.target.value)}><option value="">{f.all}</option>{f.choices.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Select>)}
      <Button type="button" variant="ghost" className="dash-reset" onClick={() => { setDraft({ ...clear, from: s.from, to: s.to }); onClear(); }}>Reset</Button>
      <Button type="submit" className="dash-apply">Apply</Button>
    </div>
    {opts.isError || sources.isError ? <p className="px-5 pb-3 text-[12px] text-required" role="alert">Some filter choices could not load. <button type="button" className="underline" onClick={() => { void opts.refetch(); void sources.refetch(); }}>Retry</button></p> : null}
  </form>;
}
