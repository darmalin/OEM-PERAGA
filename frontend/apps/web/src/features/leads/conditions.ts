import { countryName } from "@/lib/countries";
import { type LabelGroup, options } from "@/lib/labels";

/** Filter-button conditions. Mirrors the backend whitelist (visitors/rules.py CONDITION_FIELDS). */
export type Kind = "text" | "choice" | "bool" | "date" | "number";
export type Op = "contains" | "equals" | "starts_with" | "is" | "is_not" | "is_set" | "not_set" | "between" | "before" | "after" | "gt" | "lt";
export type Value = string | number | boolean | string[];
export type Condition = { field: string; op: Op; value?: Value };

/** Where a choice field gets its options: a label group, or data loaded for the page. */
type ChoiceSource = LabelGroup | "lead_sources" | "countries" | "owners" | "teams";

export type FieldDef = { key: string; label: string; kind: Kind; choices?: ChoiceSource; required?: boolean };

export const FIELDS: FieldDef[] = [
  { key: "first_name", label: "Name", kind: "text", required: true },
  { key: "company_name", label: "Company Name", kind: "text" },
  { key: "email", label: "Email", kind: "text" },
  { key: "phone", label: "Phone", kind: "text" },
  { key: "registration_code", label: "Registration ID", kind: "text", required: true },
  { key: "job_title", label: "Job Title", kind: "text" },
  { key: "city", label: "City", kind: "text" },
  { key: "telemarketing_status", label: "Status", kind: "choice", choices: "telemarketing_status", required: true },
  { key: "registration_status", label: "Registration", kind: "choice", choices: "registration_status", required: true },
  { key: "qr_status", label: "QR Status", kind: "choice", choices: "qr_status", required: true },
  { key: "lead_source_id", label: "Source", kind: "choice", choices: "lead_sources" },
  { key: "source", label: "Channel", kind: "choice", choices: "source", required: true },
  { key: "country", label: "Country", kind: "choice", choices: "countries" },
  { key: "attend", label: "Attend", kind: "choice", choices: "attend" },
  { key: "buyer_type", label: "Type of Buyers", kind: "choice", choices: "buyer_type" },
  { key: "lead_owner_id", label: "Lead Owner", kind: "choice", choices: "owners" },
  { key: "team_id", label: "Team", kind: "choice", choices: "teams", required: true },
  { key: "is_valid_lead", label: "Valid Lead", kind: "bool" },
  { key: "is_invalid", label: "Invalid", kind: "bool" },
  { key: "b2b_matching", label: "B2B Matching", kind: "bool" },
  { key: "lead_date", label: "Lead Date", kind: "date" },
  { key: "last_call_at", label: "Last Call", kind: "date" },
  { key: "next_followup_at", label: "Next Follow-up", kind: "date" },
  { key: "created_at", label: "Created On", kind: "date" },
  { key: "call_attempts", label: "Call Attempts", kind: "number" },
];

const BY_KEY = new Map(FIELDS.map((f) => [f.key, f]));
export const fieldDef = (key: string): FieldDef | undefined => BY_KEY.get(key);

const SET: Op[] = ["is_set", "not_set"];
const OPS: Record<Kind, Op[]> = {
  text: ["contains", "equals", "starts_with", ...SET],
  choice: ["is", "is_not", ...SET],
  bool: ["is"],
  date: ["between", "before", "after", ...SET],
  number: ["equals", "gt", "lt"],
};

/** Required fields are never empty, so "is set" / "is not set" are not offered for them. */
export function opsFor(f: FieldDef): Op[] {
  return f.required ? OPS[f.kind].filter((o) => !SET.includes(o)) : OPS[f.kind];
}

const OP_LABELS: Record<Op, string> = {
  contains: "contains",
  equals: "equals",
  starts_with: "starts with",
  is: "is",
  is_not: "is not",
  is_set: "is set",
  not_set: "is not set",
  between: "between",
  before: "before",
  after: "after",
  gt: "greater than",
  lt: "less than",
};
export const opLabel = (op: Op, kind: Kind): string => (kind === "number" && op === "equals" ? "equals" : OP_LABELS[op]);

export const needsValue = (op: Op): boolean => !SET.includes(op);

export function blankCondition(key = FIELDS[0]!.key): Condition {
  const f = fieldDef(key)!;
  return { field: key, op: opsFor(f)[0]!, value: f.kind === "bool" ? true : undefined };
}

/** Why a row cannot be applied yet, or null when it is complete. */
export function problem(c: Condition): string | null {
  const f = fieldDef(c.field);
  if (!f || !opsFor(f).includes(c.op)) return "Choose a field and an operator.";
  if (!needsValue(c.op)) return null;
  const v = c.value;
  switch (f.kind) {
    case "text":
      if (typeof v !== "string" || !v.trim()) return "Enter a value.";
      if (f.key === "phone" && v.replace(/\D/g, "").length < 4) return "Enter at least 4 digits.";
      return null;
    case "choice":
      return typeof v === "string" && v ? null : "Choose a value.";
    case "bool":
      return typeof v === "boolean" ? null : "Choose yes or no.";
    case "date":
      if (c.op === "between") {
        if (!Array.isArray(v) || !v[0] || !v[1]) return "Enter both dates.";
        return v[1] < v[0] ? "The end date is before the start date." : null;
      }
      return typeof v === "string" && v ? null : "Enter a date.";
    case "number":
      return typeof v === "number" && Number.isInteger(v) && v >= 0 ? null : "Enter a whole number.";
  }
}

export type ChoiceData = {
  leadSources: { id: string; name: string }[];
  countries: string[];
  owners: { id: string; name: string }[];
  teams: { id: string; name: string }[];
};

export function choicesFor(f: FieldDef, data: ChoiceData): { value: string; label: string }[] {
  switch (f.choices) {
    case undefined:
      return [];
    case "lead_sources":
      return data.leadSources.map((o) => ({ value: o.id, label: o.name }));
    case "countries":
      return data.countries.map((c) => ({ value: c, label: countryName(c) }));
    case "owners":
      return data.owners.map((o) => ({ value: o.id, label: o.name }));
    case "teams":
      return data.teams.map((o) => ({ value: o.id, label: o.name }));
    default:
      return options(f.choices);
  }
}

/** "City contains Hanoi", for the chips under the filter bar. */
export function describe(c: Condition, data: ChoiceData): string {
  const f = fieldDef(c.field);
  if (!f) return c.field;
  const head = `${f.label} ${opLabel(c.op, f.kind)}`;
  if (!needsValue(c.op)) return head;
  const v = c.value;
  if (v === undefined || v === "") return head;
  if (f.kind === "bool") return `${f.label} is ${v ? "yes" : "no"}`;
  if (Array.isArray(v)) return `${head} ${v[0]} and ${v[1]}`;
  if (f.kind === "choice") return `${head} ${choicesFor(f, data).find((o) => o.value === v)?.label ?? String(v)}`;
  return `${head} ${String(v)}`;
}
