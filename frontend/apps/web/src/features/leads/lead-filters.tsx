import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { z } from "zod";

import { campaignLinksQuery } from "@/features/campaigns/queries";
import { useMe } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useEdition } from "@/lib/edition";
import { SelectFilter, TextFilter } from "@/ui/filters";

import { type ChoiceData, type Condition, FIELDS, type Op } from "./conditions";
import { ConditionChips, FilterButton } from "./filter-button";
import { leadFilterOptionsQuery, leadSourcesQuery } from "./queries";

const condition = z.object({
  field: z.string(),
  op: z.string() as z.ZodType<Op>,
  value: z.union([z.string(), z.number(), z.boolean(), z.array(z.string())]).optional(),
});

/** URL search shared by the list and the board, so the board's "more" link lands on the same leads. */
export const leadFilterSearch = {
  // Per-field row (Frappe standard filters): text matches anywhere in the field.
  code: z.string().optional(),
  name: z.string().optional(),
  email: z.string().optional(),
  phone: z.string().optional(),
  company: z.string().optional(),
  // Exhibition Type (edition) filter; absent means every edition the user can read.
  edition: z.string().optional(),
  // A user id, "me", or "none" for unassigned leads.
  owner: z.string().optional(),
  // Stacked conditions from the Filter button.
  f: z.array(condition).optional(),
};
export const leadFilterSchema = z.object(leadFilterSearch);
export type LeadFilterSearch = z.infer<typeof leadFilterSchema>;
export const FILTER_KEYS = Object.keys(leadFilterSearch) as (keyof LeadFilterSearch)[];

/** Only the filter keys of a route's search (drops page, sort, and the like). */
export function pickFilters(s: LeadFilterSearch): LeadFilterSearch {
  return Object.fromEntries(FILTER_KEYS.filter((k) => s[k] !== undefined).map((k) => [k, s[k]]));
}

export const hasFilters = (s: LeadFilterSearch): boolean => FILTER_KEYS.some((k) => s[k] !== undefined);

/** The board's columns are the statuses: a Status condition there would empty the others. */
const BOARD_EXCLUDE = ["telemarketing_status"];

/** Query parameters for GET /visitor-leads from the per-field row and the Filter button. */
export function filterQuery(s: LeadFilterSearch, meId: string, board = false) {
  const text: [string, string | undefined][] = [
    ["registration_code", s.code],
    ["first_name", s.name],
    ["email", s.email],
    ["company_name", s.company],
    // Phone matches digits only; under 4 digits would match almost everything.
    ["phone", s.phone && s.phone.replace(/\D/g, "").length >= 4 ? s.phone : undefined],
  ];
  const conds: Condition[] = [
    ...text.filter(([, v]) => v).map(([field, value]) => ({ field, op: "contains" as const, value })),
    ...(s.f ?? []).filter((c) => !board || !BOARD_EXCLUDE.includes(c.field)),
  ];
  return {
    edition_id: s.edition,
    lead_owner_id: s.owner === "me" ? meId : s.owner && s.owner !== "none" ? s.owner : undefined,
    unassigned: s.owner === "none" ? true : undefined,
    filters: conds.length ? JSON.stringify(conds) : undefined,
  };
}

function useChoiceData(edition: string | undefined): ChoiceData {
  const sources = useQuery(leadSourcesQuery(true));
  const filterOptions = useQuery(leadFilterOptionsQuery(edition));
  const campaigns = useQuery(campaignLinksQuery(edition));
  return {
    leadSources: (sources.data ?? []).map((o) => ({ id: o.id, name: o.is_active ? o.name : `${o.name} (inactive)` })),
    countries: filterOptions.data?.countries ?? [],
    owners: filterOptions.data?.owners ?? [],
    teams: filterOptions.data?.teams ?? [],
    campaigns: (campaigns.data ?? []).map((c) => ({ id: c.id, name: c.name })),
  };
}

/**
 * The per-field row, the Filter button, and the applied chips. On a phone only Name and
 * Exhibition Type stay out when empty; the rest are in the Filter button.
 */
export function LeadFilterFields({
  s,
  set,
  board = false,
  children,
}: {
  s: LeadFilterSearch;
  set: (patch: Partial<LeadFilterSearch>) => void;
  board?: boolean;
  /** Extra controls placed before Lead Owner (the list's Status). */
  children?: ReactNode;
}) {
  const me = useMe();
  const { editions } = useEdition();
  const data = useChoiceData(s.edition);
  const fields = board ? FIELDS.filter((f) => !BOARD_EXCLUDE.includes(f.key)) : FIELDS;
  const applied = (s.f ?? []).filter((c) => !board || !BOARD_EXCLUDE.includes(c.field));
  const setF = (f: Condition[]) => set({ f: f.length ? f : undefined });
  const phoneHidden = (v: string | undefined) => (v ? undefined : "max-sm:hidden");
  const owners = [
    { value: "me", label: "Me" },
    { value: "none", label: "Unassigned" },
    ...data.owners.filter((o) => o.id !== me.user.id).map((o) => ({ value: o.id, label: o.name })),
  ];

  return (
    <>
      <TextFilter className={phoneHidden(s.code)} label="Registration ID" value={s.code} onChange={(code) => set({ code })} />
      <TextFilter label="Name" value={s.name} onChange={(name) => set({ name })} />
      <TextFilter className={phoneHidden(s.email)} label="Email" value={s.email} onChange={(email) => set({ email })} inputMode="email" />
      <TextFilter className={phoneHidden(s.phone)} label="Phone" value={s.phone} onChange={(phone) => set({ phone })} inputMode="tel" />
      <TextFilter className={phoneHidden(s.company)} label="Company" value={s.company} onChange={(company) => set({ company })} />
      <SelectFilter className="min-w-[128px]" label="Exhibition Type" value={s.edition} onChange={(edition) => set({ edition, owner: s.owner === "me" || s.owner === "none" ? s.owner : undefined })} options={editions.map((e) => ({ value: e.id, label: e.code }))} />
      {children}
      <SelectFilter className={cn("min-w-[128px]", phoneHidden(s.owner))} label="Lead Owner" allLabel="Anyone" value={s.owner} onChange={(owner) => set({ owner })} options={owners} />
      <FilterButton value={applied} onChange={setF} data={data} fields={fields} />
    </>
  );
}

/** Applied Filter-button conditions as chips, below the bar. */
export function LeadFilterChips({ s, set, board = false }: { s: LeadFilterSearch; set: (patch: Partial<LeadFilterSearch>) => void; board?: boolean }) {
  const data = useChoiceData(s.edition);
  const applied = (s.f ?? []).filter((c) => !board || !BOARD_EXCLUDE.includes(c.field));
  return <ConditionChips value={applied} onChange={(f) => set({ f: f.length ? f : undefined })} data={data} />;
}
