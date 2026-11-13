import { ApiError, api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { z } from "zod";

import { type BoothChoice, BoothPicker } from "@/features/exhibitors/booth-picker";
import { type ExhibitorLead, exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { type Quotation, type QuotationInput, type QuotationPreview, quotationQuery, quotationSettingsQuery, type QuotationSettings } from "@/features/quotations/queries";
import { QuotationSummary } from "@/features/quotations/summary";
import { formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/quotations/new")({
  validateSearch: z.object({ replaces: z.string().optional() }),
  component: NewQuotation,
});

interface TermRow {
  label: string;
  percent: string;
  due_on: string;
}

interface Values {
  stand_type: "RAW" | "SHELL";
  currency: string;
  booth: { id: string | null; code: string } | null;
  width_m: string;
  length_m: string;
  area_sqm: string;
  complimentary_sqm: string;
  stand_rate: string;
  raw_rate: string;
  discount_label: string;
  discount_percent: string;
  vat: boolean;
  terms: TermRow[];
  issued_on: string;
  recipient_company: string;
  recipient_address: string;
  attention: string;
  includes: string;
  notes: string;
}

const NUMBER = /^\d+(\.\d{1,2})?$/;

function rateOf(s: QuotationSettings, currency: string, stand: string): string {
  return s.rates.find((r) => r.currency === currency && r.stand_type === stand)?.rate ?? "";
}

function initial(s: QuotationSettings, lead: { company_name: string; contact_name: string; booth_id?: string | null; booth_code?: string | null }, from?: Quotation): Values {
  const currencies = [...new Set(s.rates.map((r) => r.currency))];
  const currency = from?.currency ?? (currencies.includes("IDR") ? "IDR" : (currencies[0] ?? "IDR"));
  const stand = (from?.stand_type ?? "RAW") as "RAW" | "SHELL";
  return {
    stand_type: stand,
    currency,
    booth: from ? (from.booth_code ? { id: from.booth_id ?? null, code: from.booth_code } : null) : lead.booth_id && lead.booth_code ? { id: lead.booth_id, code: lead.booth_code } : null,
    width_m: from?.width_m ? String(Number(from.width_m)) : "",
    length_m: from?.length_m ? String(Number(from.length_m)) : "",
    area_sqm: from && !from.width_m ? String(Number(from.area_sqm)) : "",
    complimentary_sqm: from ? String(Number(from.complimentary_sqm)) : "0",
    stand_rate: from ? String(Number(from.stand_rate)) : rateOf(s, currency, stand),
    raw_rate: from ? String(Number(from.raw_rate)) : rateOf(s, currency, "RAW"),
    discount_label: from?.discount_label ?? s.discount_label,
    discount_percent: from ? String(Number(from.discount_percent)) : "0",
    vat: from ? Number(from.vat_rate) > 0 : currency === "IDR",
    terms: (from?.terms ?? s.terms).map((t) => ({ label: t.label, percent: String(Number(t.percent)), due_on: t.due_on ?? "" })),
    issued_on: "",
    recipient_company: from?.recipient_company ?? lead.company_name,
    recipient_address: from?.recipient_address ?? "",
    attention: from?.attention ?? lead.contact_name,
    includes: from?.includes ?? "",
    notes: from?.notes ?? "",
  };
}

function body(v: Values, replaces?: string): QuotationInput {
  const opt = (x: string) => (x.trim() ? x.trim() : null);
  const hasSize = v.width_m && v.length_m;
  return {
    stand_type: v.stand_type,
    currency: v.currency,
    booth_id: v.booth?.id ?? null,
    booth_code: v.booth && !v.booth.id ? v.booth.code : null,
    width_m: hasSize ? v.width_m : null,
    length_m: hasSize ? v.length_m : null,
    area_sqm: hasSize ? null : opt(v.area_sqm),
    complimentary_sqm: v.complimentary_sqm || "0",
    stand_rate: opt(v.stand_rate),
    raw_rate: opt(v.raw_rate),
    discount_label: opt(v.discount_label),
    discount_percent: v.discount_percent || "0",
    vat: v.vat,
    terms: v.terms.map((t) => ({ label: t.label.trim(), percent: t.percent, due_on: t.due_on || null })),
    issued_on: opt(v.issued_on),
    recipient_company: opt(v.recipient_company),
    recipient_address: opt(v.recipient_address),
    attention: opt(v.attention),
    includes: opt(v.includes),
    notes: opt(v.notes),
    replaces_id: replaces ?? null,
  };
}

/** Errors the browser can tell before asking the server. */
function check(v: Values): Record<string, string> {
  const e: Record<string, string> = {};
  const hasSize = v.width_m || v.length_m;
  if (hasSize) {
    if (!NUMBER.test(v.width_m) || Number(v.width_m) <= 0) e.width_m = "Enter the width in metres, e.g. 6.";
    if (!NUMBER.test(v.length_m) || Number(v.length_m) <= 0) e.length_m = "Enter the length in metres, e.g. 21.";
  } else if (!v.booth?.id && (!NUMBER.test(v.area_sqm) || Number(v.area_sqm) <= 0)) {
    e.width_m = "Enter the width and length, or the area.";
  }
  for (const k of ["complimentary_sqm", "discount_percent", "stand_rate", "raw_rate"] as const) {
    if (v[k] && !NUMBER.test(v[k])) e[k] = "Enter a number, e.g. 25.";
  }
  if (Number(v.discount_percent) > 100) e.discount_percent = "At most 100%.";
  const total = v.terms.reduce((s, t) => s + Number(t.percent || 0), 0);
  if (v.terms.some((t) => !t.label.trim() || !NUMBER.test(t.percent))) e.terms = "Each term needs a name and a percentage.";
  else if (Math.round(total * 100) !== 10000) e.terms = `The terms add up to ${total}%, not 100%.`;
  return e;
}

function NewQuotation() {
  const { leadId } = Route.useParams();
  const { replaces } = Route.useSearch();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const settings = useQuery({ ...quotationSettingsQuery(lead.data?.edition_id ?? ""), enabled: Boolean(lead.data) });
  const from = useQuery({ ...quotationQuery(replaces ?? ""), enabled: Boolean(replaces) });
  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };

  if (lead.isPending || settings.isPending || (replaces && from.isPending)) {
    return <Page><PageHead title="New Quotation" back={back} /><Panel><FormSkeleton /></Panel></Page>;
  }
  const err = lead.error ?? settings.error ?? from.error;
  if (err || !lead.data || !settings.data) {
    return <Page><PageHead title="New Quotation" back={back} /><Panel><ErrorState error={err} /></Panel></Page>;
  }
  return <QuotationForm key={replaces ?? "new"} leadId={leadId} lead={lead.data} settings={settings.data} from={replaces ? from.data : undefined} back={back} />;
}

function QuotationForm({ leadId, lead, settings, from, back }: {
  leadId: string;
  lead: ExhibitorLead;
  settings: QuotationSettings;
  from?: Quotation;
  back: { to: string; label: string; params: Record<string, string> };
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [v, setV] = useState<Values>(() => initial(settings, lead, from));
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<QuotationPreview | null>(null);
  const [serverError, setServerError] = useState<{ message: string; fields: Record<string, string> } | null>(null);
  const errors = useMemo(() => check(v), [v]);
  const set = <K extends keyof Values>(key: K, value: Values[K]) => setV((s) => ({ ...s, [key]: value }));
  const currencies = [...new Set([...settings.rates.map((r) => r.currency), v.currency])];
  const payload = useMemo(() => JSON.stringify(body(v, from?.id)), [v, from?.id]);
  const valid = Object.keys(errors).length === 0;

  // The summary follows the form after a short pause; the server does the arithmetic.
  useEffect(() => {
    if (!valid) return;
    let live = true;
    const t = window.setTimeout(() => {
      call(api.POST("/api/v1/exhibitor-leads/{lead_id}/quotations/preview", { params: { path: { lead_id: leadId } }, body: JSON.parse(payload) as QuotationInput }))
        .then((p) => {
          if (!live) return;
          setPreview(p);
          setServerError(null);
        })
        .catch((e: unknown) => {
          if (!live) return;
          setPreview(null);
          setServerError(e instanceof ApiError ? { message: e.message, fields: e.fields } : { message: "Could not compute the summary.", fields: {} });
        });
    }, 400);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [payload, valid, leadId]);

  const changeRates = (currency: string, stand: "RAW" | "SHELL") => {
    setV((s) => ({
      ...s,
      currency,
      stand_type: stand,
      stand_rate: rateOf(settings, currency, stand),
      raw_rate: rateOf(settings, currency, "RAW"),
      vat: currency === s.currency ? s.vat : currency === "IDR",
    }));
  };

  const create = async () => {
    setBusy(true);
    try {
      const made = await call(api.POST("/api/v1/exhibitor-leads/{lead_id}/quotations", { params: { path: { lead_id: leadId } }, body: JSON.parse(payload) as QuotationInput }));
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", leadId, "quotations"] });
      if (from) void queryClient.invalidateQueries({ queryKey: ["quotation", from.id] });
      notifySuccess(`Quotation ${made.number} created`, formatMoney(made.total_amount, made.currency));
      await navigate({ to: "/app/exhibitor-leads/$leadId/quotations/$quotationId", params: { leadId, quotationId: made.id } });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const fieldError = (k: string) => errors[k] ?? serverError?.fields[k];
  const pickBooth = (c: BoothChoice) => {
    if (c.kind === "listed") {
      setV((s) => ({ ...s, booth: { id: c.booth.id, code: c.booth.code }, area_sqm: s.width_m ? s.area_sqm : String(Number(c.booth.area_sqm)) }));
    } else {
      set("booth", { id: null, code: c.code });
    }
  };

  return (
    <Page>
      <PageHead title={from ? `Revise ${from.number}` : "New Quotation"} back={back} meta={from ? "The new quotation gets its own number; this one becomes Superseded." : `For ${lead.company_name}. Check the summary, then create it.`} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_460px]">
        <Panel className="min-w-0">
          <Section title="Recipient">
            <FieldGrid>
              <Field label="Company" required>{(p) => <Input {...p} value={v.recipient_company} maxLength={300} onChange={(e) => set("recipient_company", e.target.value)} />}</Field>
              <Field label="Attention" help="Printed as “Dear, …”, e.g. Ms. Novy.">{(p) => <Input {...p} value={v.attention} maxLength={200} onChange={(e) => set("attention", e.target.value)} />}</Field>
              <Field label="Address" className="md:col-span-2 lg:col-span-3" help="Up to two lines, as on the letter.">{(p) => <Textarea {...p} rows={2} value={v.recipient_address} maxLength={1000} onChange={(e) => set("recipient_address", e.target.value)} />}</Field>
            </FieldGrid>
          </Section>
          <Section title="Space">
            <FieldGrid>
              <Field label="Stand" required>
                {(p) => (
                  <Select {...p} value={v.stand_type} onChange={(e) => changeRates(v.currency, e.target.value as "RAW" | "SHELL")}>
                    <option value="RAW">Raw Space</option>
                    <option value="SHELL">Shell Scheme</option>
                  </Select>
                )}
              </Field>
              <Field label="Currency" required>
                {(p) => (
                  <Select {...p} value={v.currency} onChange={(e) => changeRates(e.target.value, v.stand_type)}>
                    {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Booth" help="Optional. A listed booth, or any code typed in.">
                {(p) =>
                  v.booth ? (
                    <div className="flex h-9 items-center justify-between rounded-[8px] border border-line px-3 text-[14px]">
                      <span className="tabular font-medium">{v.booth.code}{v.booth.id ? "" : " (not in the list)"}</span>
                      <Button variant="ghost" size="sm" aria-label="Remove the booth" onClick={() => set("booth", null)}><X aria-hidden /></Button>
                    </div>
                  ) : (
                    <BoothPicker editionId={lead.edition_id} canAdd onPick={pickBooth} inputId={p.id} describedBy={p["aria-describedby"]} addLabel={(code) => `Use code “${code}”`} placeholder="Search or type a booth code" />
                  )
                }
              </Field>
              <Field label="Width (m)" error={fieldError("width_m")}>{(p) => <Input {...p} inputMode="decimal" value={v.width_m} onChange={(e) => set("width_m", e.target.value.trim())} />}</Field>
              <Field label="Length (m)" error={fieldError("length_m")}>{(p) => <Input {...p} inputMode="decimal" value={v.length_m} onChange={(e) => set("length_m", e.target.value.trim())} />}</Field>
              <Field label="Area (sqm)" help={v.width_m && v.length_m ? `Width x length: ${Number(v.width_m) * Number(v.length_m) || 0} sqm.` : "When there is no width and length."} error={fieldError("area_sqm")}>
                {(p) => <Input {...p} inputMode="decimal" disabled={Boolean(v.width_m && v.length_m)} value={v.width_m && v.length_m ? "" : v.area_sqm} onChange={(e) => set("area_sqm", e.target.value.trim())} />}
              </Field>
              <Field label="Complimentary Space (sqm)" help="Free space, not charged." error={fieldError("complimentary_sqm")}>{(p) => <Input {...p} inputMode="decimal" value={v.complimentary_sqm} onChange={(e) => set("complimentary_sqm", e.target.value.trim())} />}</Field>
            </FieldGrid>
          </Section>
          <Section title="Price">
            <FieldGrid>
              <Field label={`${v.stand_type === "SHELL" ? "Shell Scheme" : "Raw Space"} Rate per sqm (${v.currency})`} required help="From the quotation settings; change it for this company if needed." error={fieldError("stand_rate")}>
                {(p) => <Input {...p} inputMode="decimal" value={v.stand_rate} onChange={(e) => set("stand_rate", e.target.value.trim())} />}
              </Field>
              {v.stand_type === "SHELL" ? (
                <Field label={`Raw Space Rate per sqm (${v.currency})`} help="The discount is a share of the raw space cost." error={fieldError("raw_rate")}>
                  {(p) => <Input {...p} inputMode="decimal" value={v.raw_rate} onChange={(e) => set("raw_rate", e.target.value.trim())} />}
                </Field>
              ) : null}
              <Field label="Discount (%)" error={fieldError("discount_percent")}>{(p) => <Input {...p} inputMode="decimal" value={v.discount_percent} onChange={(e) => set("discount_percent", e.target.value.trim())} />}</Field>
              <Field label="Discount Name" help="Special Discount, Early Bird, …">{(p) => <Input {...p} value={v.discount_label} maxLength={60} onChange={(e) => set("discount_label", e.target.value)} />}</Field>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-[13px]">
                  <Checkbox checked={v.vat} onCheckedChange={(c) => set("vat", c === true)} />
                  VAT {Number(settings.vat_rate)}% on a {settings.vat_base_num}/{settings.vat_base_den} tax base
                </label>
              </div>
            </FieldGrid>
          </Section>
          <Section title="Terms of Payment">
            <div className="flex flex-col gap-3">
              {v.terms.map((t, i) => (
                <div key={i} className="grid grid-cols-[minmax(0,1fr)_96px_160px_auto] items-end gap-3 max-sm:grid-cols-2">
                  <Field label={`Term ${i + 1}`}>{(p) => <Input {...p} value={t.label} maxLength={60} onChange={(e) => set("terms", v.terms.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />}</Field>
                  <Field label="%">{(p) => <Input {...p} inputMode="decimal" value={t.percent} onChange={(e) => set("terms", v.terms.map((x, j) => (j === i ? { ...x, percent: e.target.value.trim() } : x)))} />}</Field>
                  <Field label="Date">{(p) => <Input {...p} type="date" value={t.due_on} onChange={(e) => set("terms", v.terms.map((x, j) => (j === i ? { ...x, due_on: e.target.value } : x)))} />}</Field>
                  <Button variant="ghost" aria-label={`Remove term ${i + 1}`} disabled={v.terms.length === 1} onClick={() => set("terms", v.terms.filter((_, j) => j !== i))}><Trash2 aria-hidden /></Button>
                </div>
              ))}
              {errors.terms ? <p className="text-[12px] text-required">{errors.terms}</p> : null}
              <div>
                <Button variant="ghost" size="sm" disabled={v.terms.length >= 10} onClick={() => set("terms", [...v.terms, { label: "", percent: "", due_on: "" }])}><Plus aria-hidden />Add Term</Button>
              </div>
            </div>
          </Section>
          <Section title="Letter" defaultOpen={Boolean(from)}>
            <FieldGrid>
              <Field label="Date" help="Today when empty.">{(p) => <Input {...p} type="date" value={v.issued_on} onChange={(e) => set("issued_on", e.target.value)} />}</Field>
              <Field label="Include" className="md:col-span-2" help={v.stand_type === "SHELL" ? "Empty uses the shell scheme inclusions from the settings." : "What the price includes, if anything."}>
                {(p) => <Input {...p} value={v.includes} maxLength={1000} onChange={(e) => set("includes", e.target.value)} />}
              </Field>
              <Field label="Notes" className="md:col-span-2 lg:col-span-3" help="Extra lines printed under the price.">{(p) => <Textarea {...p} rows={2} value={v.notes} maxLength={2000} onChange={(e) => set("notes", e.target.value)} />}</Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }} search={{ tab: "quotations" }}>Cancel</Link></Button>
            <Button variant="primary" disabled={!valid || !preview} loading={busy} onClick={() => void create()}>Create Quotation</Button>
          </FormActions>
        </Panel>
        <aside className="xl:sticky xl:top-4 xl:self-start">
          <Panel>
            <PanelHeader title={preview ? `Summary · ${preview.number}` : "Summary"} />
            <div className="p-5" aria-live="polite">
              {!valid ? (
                <p className="text-[13px] text-label">Fill in the size and the terms to see the price.</p>
              ) : serverError ? (
                <p role="alert" className="text-[13px] text-required">{serverError.message}{Object.values(serverError.fields).length ? `: ${Object.values(serverError.fields).join(" ")}` : ""}</p>
              ) : preview ? (
                <>
                  <QuotationSummary q={preview} />
                  <p className="mt-4 text-[12px] text-label">The number is taken when you create the quotation; another one made meanwhile may take it first.</p>
                </>
              ) : (
                <p className="text-[13px] text-label">Computing</p>
              )}
            </div>
          </Panel>
        </aside>
      </div>
    </Page>
  );
}
