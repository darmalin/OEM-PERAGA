import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Textarea } from "@/ui/input";

import type { DetailsType, OrderForm } from "./queries";

/** orders/rules.py OptionKind. */
type OptionKind = "PRODUCT_CATEGORY" | "STAND_SERVICE" | "OFFICIAL_CONTRACTOR" | "OFFICIAL_FORWARDER" | "SEMINAR_DATE";

/** Which choices each question set uses (orders/rules.py DETAILS_OPTION_KINDS). */
export const OPTION_KINDS: Record<DetailsType, OptionKind[]> = {
  directory_listing: ["PRODUCT_CATEGORY"],
  advertising: [],
  social_media: ["PRODUCT_CATEGORY"],
  stand_service: ["STAND_SERVICE", "OFFICIAL_CONTRACTOR"],
  exhibit_details: [],
  freight: ["OFFICIAL_FORWARDER"],
  badges_visa: [],
  seminar: ["SEMINAR_DATE"],
  parking: [],
};

const KIND_LABELS: Record<OptionKind, { label: string; help: string }> = {
  PRODUCT_CATEGORY: { label: "Product Categories", help: "One per line, e.g. Fabrics." },
  STAND_SERVICE: { label: "Stand Services", help: "One per line, e.g. Standard booth, Raw space." },
  OFFICIAL_CONTRACTOR: { label: "Official Contractors", help: "One company per line." },
  OFFICIAL_FORWARDER: { label: "Official Freight Forwarders", help: "One company per line." },
  SEMINAR_DATE: { label: "Seminar Dates", help: "One per line, as exhibitors should read it, e.g. 15 April 2027." },
};

export const optionsQuery = (formId: string) => ({
  queryKey: ["order-forms", "form", formId, "options"],
  queryFn: () => call(api.GET("/api/v1/order-forms/{form_id}/options", { params: { path: { form_id: formId } } })),
});

/** Settings section: the choices exhibitors pick from in this form's questions. */
export function OptionsSection({ form }: { form: OrderForm }) {
  const kinds = form.details_type ? OPTION_KINDS[form.details_type] : [];
  const q = useQuery({ ...optionsQuery(form.id), enabled: kinds.length > 0 });
  if (kinds.length === 0) return null;
  return (
    <Section title="Choices">
      <p className="mb-4 max-w-2xl text-[13px] text-muted">
        What exhibitors choose from in the questions. Changing a list does not change answers already sent.
      </p>
      {q.isPending ? <p className="text-[13px] text-label">Loading</p> : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {kinds.map((kind) => (
            <OptionList key={`${kind}-${(q.data?.options[kind] ?? []).join("|")}`} formId={form.id} kind={kind} values={q.data?.options[kind] ?? []} />
          ))}
        </div>
      )}
    </Section>
  );
}

function OptionList({ formId, kind, values }: { formId: string; kind: OptionKind; values: string[] }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState(values.join("\n"));
  const [busy, setBusy] = useState(false);
  const lines = text.split("\n").map((v) => v.trim()).filter(Boolean);
  const dirty = lines.join("\n") !== values.join("\n");
  const info = KIND_LABELS[kind];
  const save = async () => {
    setBusy(true);
    try {
      const out = await call(api.PUT("/api/v1/order-forms/{form_id}/options", { params: { path: { form_id: formId } }, body: { kind, values: lines } }));
      queryClient.setQueryData(optionsQuery(formId).queryKey, out);
      notifySuccess(`${info.label} saved`, `${out.options[kind]?.length ?? 0} choices`);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <Field label={info.label} help={info.help}>
        {(p) => <Textarea {...p} rows={6} value={text} onChange={(e) => setText(e.target.value)} />}
      </Field>
      <div><Button size="sm" disabled={!dirty} loading={busy} onClick={() => void save()}>Save {info.label}</Button></div>
    </div>
  );
}

// --- answers on the review page ----------------------------------------------------------

/** Question order per set (orders/details.py), for showing answers in the order asked. */
const FIELD_ORDER: Record<string, string[]> = {
  directory_listing: ["agent_or_principal", "listed_as", "brief_introduction", "product_categories", "product_details", "agent_principal_listings", "looking_for_local_agent"],
  advertising: ["logo_shape", "image_url"],
  social_media: ["product_category", "product_description", "video_link", "video_title", "video_description", "facebook", "x", "linkedin", "instagram", "youtube"],
  stand_service: ["service", "contractor", "official_contractor", "own_contractor"],
  exhibit_details: ["items", "sale_and_operation", "purchased"],
  freight: ["uses_official", "official_forwarder", "non_official", "shipments"],
  badges_visa: ["company_type", "badges", "vip_needed", "vip_badges", "needs_visa_letter"],
  seminar: ["topic", "date", "time", "speakers"],
  parking: ["plates"],
};
/** Column order inside rows (badges, exhibits, shipments, speakers). */
const COLUMN_ORDER = ["quantity", "full_name", "name", "company", "description", "designation", "gender", "country", "title_of_speech", "dimension", "length_m", "width_m", "height_m", "weight_kg"];

export function orderedKeys(keys: string[], order: string[]): string[] {
  return [...order.filter((k) => keys.includes(k)), ...keys.filter((k) => !order.includes(k))];
}

const VALUES: Record<string, string> = {
  AGENT: "Agent", PRINCIPAL: "Principal", MANUFACTURER: "Manufacturer", DISTRIBUTOR_AGENT: "Distributor / Agent",
  LOOKING_FOR_DISTRIBUTOR: "Looking for a distributor", NONE: "None of the above", SQUARE: "Square",
  RECTANGLE: "Rectangle", OFFICIAL: "Official contractor", OWN: "Own contractor", SALE_OPERATED: "For sale, operated",
  SALE_DISPLAY_ONLY: "For sale, display only", NOT_FOR_SALE_DISPLAY_ONLY: "Not for sale, display only",
  NOT_FOR_SALE_OPERATED: "Not for sale, operated", LOCAL: "Indonesian company", OVERSEAS: "Overseas company",
  MALE: "Male", FEMALE: "Female",
};

const KEYS: Record<string, string> = {
  x: "X (Twitter)", pic: "PIC", weight_kg: "Weight (kg)", length_m: "Length (m)", width_m: "Width (m)",
  height_m: "Height (m)", vip_needed: "VIP badges", vip_badges: "VIP guests", needs_visa_letter: "Visa invitation letter",
  uses_official: "Official forwarder", non_official: "Own forwarder", own_contractor: "Own contractor",
};

function keyLabel(key: string): string {
  return KEYS[key] ?? key.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());
}

function show(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return VALUES[value] ?? value;
  return String(value);
}

/** Answers as label and value, nested rows as small tables. */
export function AnswersView({ type, answers }: { type: string; answers: Record<string, unknown> }) {
  const entries = orderedKeys(Object.keys(answers), FIELD_ORDER[type] ?? []).map((k) => [k, answers[k]] as const);
  if (entries.length === 0) return <p className="text-[13px] text-label">No answers.</p>;
  return (
    <dl className="grid grid-cols-[minmax(0,180px)_minmax(0,1fr)] gap-x-4 gap-y-3 text-[14px] max-sm:grid-cols-1">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="text-label">{keyLabel(key)}</dt>
          <dd className="min-w-0 break-words">
            {Array.isArray(value) ? (
              value.length && typeof value[0] === "object" ? <Rows rows={value as Record<string, unknown>[]} /> : (value as unknown[]).map(show).join(", ")
            ) : value && typeof value === "object" ? (
              <span className="flex flex-col">
                {Object.entries(value as Record<string, unknown>).map(([k, v]) => <span key={k}><span className="text-label">{keyLabel(k)}:</span> {show(v)}</span>)}
              </span>
            ) : show(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Rows({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = orderedKeys([...new Set(rows.flatMap((r) => Object.keys(r)))], COLUMN_ORDER);
  return (
    <div className="overflow-x-auto">
      <table className="text-[13px]">
        <thead>
          <tr className="text-left text-label">{columns.map((c) => <th key={c} scope="col" className="pr-4 pb-1 font-normal">{keyLabel(c)}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, n) => (
            <tr key={n}>{columns.map((c) => <td key={c} className="pr-4 py-0.5">{r[c] == null ? "" : show(r[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
