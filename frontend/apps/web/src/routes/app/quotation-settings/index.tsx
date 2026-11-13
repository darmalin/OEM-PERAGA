import { api, ApiError, call, type Schemas, upload } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { type QuotationSettings, quotationSettingsQuery } from "@/features/quotations/queries";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton, NoAccess, NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/quotation-settings/")({ component: QuotationSettingsPage });

/** The rate grid: one rate per currency and stand type; an empty box means "no rate". */
const RATE_CELLS = [
  ["IDR", "RAW", "Raw Space (IDR)"],
  ["IDR", "SHELL", "Shell Scheme (IDR)"],
  ["USD", "RAW", "Raw Space (USD)"],
  ["USD", "SHELL", "Shell Scheme (USD)"],
] as const;
const NUMBER = /^\d+(\.\d{1,2})?$/;

interface Values {
  code: string;
  company_code: string;
  start_number: string;
  place: string;
  letter_name: string;
  event_text: string;
  rates: Record<string, string>;
  shell_includes: string;
  discount_label: string;
  vat_rate: string;
  vat_base_num: string;
  vat_base_den: string;
  terms: { label: string; percent: string; due_on: string }[];
  signer_name: string;
  signer_title: string;
}

function toValues(s: QuotationSettings): Values {
  return {
    code: s.code ?? "",
    company_code: s.company_code,
    start_number: String(s.start_number),
    place: s.place,
    letter_name: s.letter_name ?? "",
    event_text: s.event_text ?? "",
    rates: Object.fromEntries(s.rates.map((r) => [`${r.currency}:${r.stand_type}`, String(Number(r.rate))])),
    shell_includes: s.shell_includes ?? "",
    discount_label: s.discount_label,
    vat_rate: String(Number(s.vat_rate)),
    vat_base_num: String(s.vat_base_num),
    vat_base_den: String(s.vat_base_den),
    terms: s.terms.map((t) => ({ label: t.label, percent: String(Number(t.percent)), due_on: t.due_on ?? "" })),
    signer_name: s.signer_name ?? "",
    signer_title: s.signer_title ?? "",
  };
}

function QuotationSettingsPage() {
  const me = useMe();
  const { edition } = useEdition();
  const q = useQuery({ ...quotationSettingsQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  if (!edition) return <Page><NoEdition /></Page>;
  if (!can(me, "booth.manage")) return <Page><NoAccess /></Page>;
  return (
    <Page className="max-w-[1000px]">
      <PageHead edition title="Quotation Settings" meta={`What every quotation of ${edition.code} starts from. Quotations already made keep what they printed.`} />
      {q.isPending ? <Panel><FormSkeleton /></Panel> : q.isError ? <Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel> : (
        <SettingsForm key={`${edition.id}-${q.data.version ?? 0}`} editionId={edition.id} settings={q.data} />
      )}
    </Page>
  );
}

function SettingsForm({ editionId, settings }: { editionId: string; settings: QuotationSettings }) {
  const queryClient = useQueryClient();
  const [v, setV] = useState<Values>(() => toValues(settings));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const set = <K extends keyof Values>(k: K, value: Values[K]) => setV((s) => ({ ...s, [k]: value }));

  const save = async () => {
    const e: Record<string, string> = {};
    if (!/^[A-Za-z0-9-]{1,20}$/.test(v.code.trim())) e.code = "Letters and digits, e.g. IIT.";
    if (!/^\d+$/.test(v.start_number) || Number(v.start_number) < 1) e.start_number = "A whole number, e.g. 113.";
    for (const [cur, stand] of RATE_CELLS) {
      const x = v.rates[`${cur}:${stand}`] ?? "";
      if (x && !NUMBER.test(x)) e[`rate:${cur}:${stand}`] = "Enter a number, e.g. 4850000.";
    }
    const total = v.terms.reduce((s, t) => s + Number(t.percent || 0), 0);
    if (v.terms.some((t) => !t.label.trim() || !NUMBER.test(t.percent))) e.terms = "Each term needs a name and a percentage.";
    else if (Math.round(total * 100) !== 10000) e.terms = `The terms add up to ${total}%, not 100%.`;
    setErrors(e);
    if (Object.keys(e).length) return;
    const body: Schemas["SettingsIn"] = {
      code: v.code.trim(),
      company_code: v.company_code.trim() || "PNJS",
      start_number: Number(v.start_number),
      place: v.place.trim() || "Jakarta",
      letter_name: v.letter_name.trim() || null,
      event_text: v.event_text.trim() || null,
      rates: RATE_CELLS.filter(([cur, stand]) => v.rates[`${cur}:${stand}`]).map(([cur, stand]) => ({ currency: cur, stand_type: stand, rate: v.rates[`${cur}:${stand}`] ?? "0" })),
      shell_includes: v.shell_includes.trim() || null,
      discount_label: v.discount_label.trim() || "Special Discount",
      vat_rate: v.vat_rate || "0",
      vat_base_num: Number(v.vat_base_num),
      vat_base_den: Number(v.vat_base_den),
      terms: v.terms.map((t) => ({ label: t.label.trim(), percent: t.percent, due_on: t.due_on || null })),
      signer_name: v.signer_name.trim() || null,
      signer_title: v.signer_title.trim() || null,
      version: settings.exists ? settings.version : null,
    };
    setBusy(true);
    try {
      const out = await call(api.PUT("/api/v1/editions/{edition_id}/quotation-settings", { params: { path: { edition_id: editionId } }, body }));
      queryClient.setQueryData(quotationSettingsQuery(editionId).queryKey, out);
      notifySuccess("Quotation settings saved", `Next number ${out.next_number ?? ""}`);
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fields);
      notifyError(err);
    } finally {
      setBusy(false);
    }
  };

  const sendSignature = async () => {
    if (!file || !settings.exists || settings.version == null) return;
    setFileBusy(true);
    try {
      const form = new FormData();
      form.set("file", file);
      form.set("version", String(settings.version));
      const out = await upload<QuotationSettings>(`/api/v1/editions/${editionId}/quotation-settings/signature`, form);
      queryClient.setQueryData(quotationSettingsQuery(editionId).queryKey, out);
      notifySuccess("Signature saved");
    } catch (err) {
      notifyError(err);
    } finally {
      setFileBusy(false);
    }
  };

  return (
    <Panel>
      <Section title="Number">
        <FieldGrid>
          <Field label="Quotation Code" required help="The middle of the number, e.g. IIT in 113/PNJS/IIT/VII/2026. Editions with the same code share the numbers." error={errors.code}>
            {(p) => <Input {...p} value={v.code} maxLength={20} onChange={(e) => set("code", e.target.value.toUpperCase())} />}
          </Field>
          <Field label="Start From" required help={settings.next_number ? `Next quotation this year: ${settings.next_number}.` : "The first number this year, after the ones already used in Excel."} error={errors.start_number}>
            {(p) => <Input {...p} inputMode="numeric" value={v.start_number} onChange={(e) => set("start_number", e.target.value.trim())} />}
          </Field>
          <Field label="Company Code" help="PNJS: PT. Peraga Nusantara Jaya Sakti.">{(p) => <Input {...p} value={v.company_code} maxLength={20} onChange={(e) => set("company_code", e.target.value.toUpperCase())} />}</Field>
        </FieldGrid>
      </Section>
      <Section title="Letter">
        <FieldGrid>
          <Field label="Exhibition Name in the Letter" className="md:col-span-2" help="e.g. INATEX 2027 (The 23rd Indonesia International Textile Sourcing and Apparel Production Technology Expo)">
            {(p) => <Textarea {...p} rows={2} value={v.letter_name} maxLength={500} onChange={(e) => set("letter_name", e.target.value)} />}
          </Field>
          <Field label="Place" help="Before the date: “Jakarta, July 22, 2026”.">{(p) => <Input {...p} value={v.place} maxLength={100} onChange={(e) => set("place", e.target.value)} />}</Field>
          <Field label="When and Where" className="md:col-span-2" help="After “which will be held on”, e.g. 14-17 April 2027 at JIEXPO Kemayoran.">
            {(p) => <Input {...p} value={v.event_text} maxLength={500} onChange={(e) => set("event_text", e.target.value)} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Rates per sqm">
        <FieldGrid>
          {RATE_CELLS.map(([cur, stand, text]) => (
            <Field key={`${cur}:${stand}`} label={text} error={errors[`rate:${cur}:${stand}`]} help={cur === "USD" && stand === "RAW" ? "Empty: no USD quotations." : undefined}>
              {(p) => <Input {...p} inputMode="decimal" value={v.rates[`${cur}:${stand}`] ?? ""} onChange={(e) => set("rates", { ...v.rates, [`${cur}:${stand}`]: e.target.value.trim() })} />}
            </Field>
          ))}
          <Field label="Shell Scheme Includes" className="md:col-span-2" help="Printed under the shell scheme cost.">
            {(p) => <Input {...p} value={v.shell_includes} maxLength={1000} onChange={(e) => set("shell_includes", e.target.value)} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Discount and VAT">
        <FieldGrid>
          <Field label="Discount Name" help="The default; each quotation can change it.">{(p) => <Input {...p} value={v.discount_label} maxLength={60} onChange={(e) => set("discount_label", e.target.value)} />}</Field>
          <Field label="VAT (%)" help="On IDR quotations; USD ones start without VAT.">{(p) => <Input {...p} inputMode="decimal" value={v.vat_rate} onChange={(e) => set("vat_rate", e.target.value.trim())} />}</Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tax Base" help="11 / 12">{(p) => <Input {...p} inputMode="numeric" value={v.vat_base_num} onChange={(e) => set("vat_base_num", e.target.value.trim())} />}</Field>
            <Field label="of">{(p) => <Input {...p} inputMode="numeric" value={v.vat_base_den} onChange={(e) => set("vat_base_den", e.target.value.trim())} />}</Field>
          </div>
        </FieldGrid>
      </Section>
      <Section title="Default Terms of Payment">
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
          <div><Button variant="ghost" size="sm" disabled={v.terms.length >= 10} onClick={() => set("terms", [...v.terms, { label: "", percent: "", due_on: "" }])}><Plus aria-hidden />Add Term</Button></div>
        </div>
      </Section>
      <Section title="Signed By">
        <FieldGrid>
          <Field label="Name">{(p) => <Input {...p} value={v.signer_name} maxLength={200} onChange={(e) => set("signer_name", e.target.value)} />}</Field>
          <Field label="Title">{(p) => <Input {...p} value={v.signer_title} maxLength={200} onChange={(e) => set("signer_title", e.target.value)} />}</Field>
          <Field label="Signature Image" help={settings.exists ? "PNG or JPEG, up to 2 MB. New quotations print it." : "Save the settings first."}>
            {(p) => (
              <div className="flex gap-2">
                <Input {...p} type="file" accept="image/png,image/jpeg" disabled={!settings.exists} className="min-w-0 py-1.5" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                <Button disabled={!file} loading={fileBusy} onClick={() => void sendSignature()}><Upload aria-hidden />Upload</Button>
              </div>
            )}
          </Field>
        </FieldGrid>
        {settings.has_signature ? (
          <img src={`/api/v1/editions/${editionId}/quotation-settings/signature?v=${settings.version ?? 0}`} alt="Current signature" className="mt-4 h-16 rounded-[8px] border border-line bg-white object-contain p-1" />
        ) : null}
      </Section>
      <FormActions>
        <Button variant="primary" loading={busy} onClick={() => void save()}>Save Settings</Button>
      </FormActions>
    </Panel>
  );
}
