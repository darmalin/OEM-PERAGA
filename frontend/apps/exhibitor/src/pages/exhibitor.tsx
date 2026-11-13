import { api, ApiError, call, downloadFile, type Schemas, upload } from "@ems/api";
import { Check, ChevronLeft, Download, FileUp } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { date, type ExhibitorRecord, href, label, messageOf, money, navigate, showCountdown } from "../lib";
import { BoothTag, Button, Facts, Field, Input, Notice, Panel, Progress, Status, Textarea } from "../ui";

type Contract = Schemas["ContractOut"];
type Payments = Schemas["PortalPaymentsOut"];
type Forms = Schemas["PortalOrderFormsOut"];
type Loaded = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; contract: Contract; payments: Payments; forms: Forms | null };

export function ExhibitorPage({ record, onSignedOut }: { record: ExhibitorRecord; onSignedOut: () => void }) {
  const id = record.exhibitor_lead_id;
  const [state, setState] = useState<Loaded>({ kind: "loading" });
  // Confirmation of the last change; the contract panel remounts with the new version.
  const [flash, setFlash] = useState<string | null>(null);

  const failed = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) onSignedOut();
      else setState({ kind: "error", message: messageOf(e) });
    },
    [onSignedOut],
  );

  // The confirmation is set with the reloaded contract, never before it: the panel remounts
  // with the new version, and a file picked in the old panel would be lost.
  const load = useCallback(
    (message: string | null = null) => {
      const path = { params: { path: { lead_id: id } } };
      Promise.all([
        call(api.GET("/api/v1/portal/exhibitors/{lead_id}/contract", path)),
        call(api.GET("/api/v1/portal/exhibitors/{lead_id}/payments", path)),
        // The checklist still shows without the order forms if they fail to load.
        call(api.GET("/api/v1/portal/exhibitors/{lead_id}/order-forms", path)).catch(() => null),
      ])
        .then(([contract, payments, forms]) => {
          setState({ kind: "ready", contract, payments, forms });
          setFlash(message);
        })
        .catch(failed);
    },
    [id, failed],
  );

  useEffect(() => load(), [load]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <a href={href("/")} onClick={(e) => { e.preventDefault(); navigate("/"); }} className="mb-3 inline-flex items-center gap-1 rounded-[6px] text-[14px] font-semibold text-primary hover:underline">
          <ChevronLeft className="size-4" aria-hidden />My Exhibitions
        </a>
        <Hero record={record} />
      </div>
      {state.kind === "loading" ? (
        <p role="status" className="py-10 text-center text-label">Loading</p>
      ) : state.kind === "error" ? (
        <div className="flex flex-col items-start gap-3"><Notice>{state.message}</Notice><Button onClick={() => load()}>Retry</Button></div>
      ) : (
        <>
          <Checklist leadId={id} contract={state.contract} payments={state.payments} forms={state.forms} />
          <ContractPanel
            key={state.contract.version}
            leadId={id}
            contract={state.contract}
            flash={flash}
            onChange={load}
            onError={failed}
          />
          <PaymentsPanel payments={state.payments} signed={state.contract.status === "SIGNED"} />
          <Panel title="Order Forms" id="order-forms">
            <div className="flex flex-col gap-4">
              {state.forms && state.forms.forms.length ? (
                <Progress done={doneForms(state.forms)} total={state.forms.forms.length} label="Forms done" />
              ) : null}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-[15px] text-muted">Order electricity, furniture, internet, badges, and other services for your booth.</p>
                <Button variant="primary" onClick={() => navigate(`/e/${id}/forms`)}>Open Order Forms</Button>
              </div>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function ContractPanel({
  leadId,
  contract: c,
  flash,
  onChange,
  onError,
}: {
  leadId: string;
  contract: Contract;
  flash: string | null;
  onChange: (message: string) => void;
  onError: (e: unknown) => void;
}) {
  const signed = c.status === "SIGNED";
  return (
    <Panel id="contract" title={`Contract ${c.contract_number ?? ""}`} aside={<Status value={c.status} />}>
      {flash ? <div className="mb-5"><Notice tone="green">{flash}</Notice></div> : null}
      <Facts
        items={[
          ["Booth", c.booth_code],
          ["Booth Price", money(c.booth_price, c.currency)],
          ...(Number(c.discount_amount) > 0 ? ([["Discount", money(c.discount_amount, c.currency)]] as [string, string][]) : []),
          ...(Number(c.vat_rate) > 0 ? ([[`VAT ${Number(c.vat_rate)}%`, money(c.vat_amount, c.currency)]] as [string, string][]) : []),
          ["Total", <span key="t" className="font-semibold">{money(c.total_amount, c.currency)}</span>],
          ...(c.quotation_number ? ([["Quotation", c.quotation_number]] as [string, string][]) : []),
          ...(signed ? ([["Signed", date(c.signed_at)], ["PIC", c.pic_name], ["Address", c.company_address], ["Tax ID (NPWP)", c.tax_id]] as [string, string | null][]) : []),
        ]}
      />
      {(c.payment_terms ?? []).length > 0 ? (
        <div className="mt-5">
          <p className="mb-2 text-[14px] font-semibold text-ink">Terms of payment</p>
          <ul className="flex flex-col divide-y divide-line rounded-[12px] border border-line">
            {(c.payment_terms ?? []).map((t) => (
              <li key={t.label} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5 text-[14px]">
                <span className="font-medium">{t.label} <span className="font-normal text-label">{Number(t.percent)}%</span></span>
                <span className="tabular-nums">{money(t.amount, c.currency)}{t.due_on ? <span className="text-label"> · by {date(t.due_on)}</span> : null}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {signed ? <SignedCopy leadId={leadId} /> : (
        <>
          <ContractForm leadId={leadId} contract={c} onSaved={() => onChange("Contract details saved.")} onError={onError} />
          <SignUpload leadId={leadId} contract={c} onSigned={() => onChange("Signed contract received. The contract is now final.")} />
        </>
      )}
    </Panel>
  );
}

function ContractForm({ leadId, contract: c, onSaved, onError }: { leadId: string; contract: Contract; onSaved: () => void; onError: (e: unknown) => void }) {
  const [values, setValues] = useState({ pic_name: c.pic_name ?? "", company_address: c.company_address ?? "", tax_id: c.tax_id ?? "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const dirty = values.pic_name !== (c.pic_name ?? "") || values.company_address !== (c.company_address ?? "") || values.tax_id !== (c.tax_id ?? "");
  const set = (k: keyof typeof values) => (e: { target: { value: string } }) => setValues((v) => ({ ...v, [k]: e.target.value }));

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setMessage(null);
    try {
      await call(api.PATCH("/api/v1/portal/exhibitors/{lead_id}/contract", { params: { path: { lead_id: leadId } }, body: { ...values, version: c.version } }));
      onSaved();
    } catch (err) {
      if (err instanceof ApiError && err.code === "VERSION_CONFLICT") setMessage("The contract was changed by your sales contact meanwhile. Reload the page to see the latest version.");
      else if (err instanceof ApiError && err.status !== 401) { setErrors(err.fields); setMessage(err.message); }
      else onError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={(e) => void save(e)} noValidate className="mt-6 flex flex-col gap-4 border-t border-line pt-6">
      <div>
        <h3 className="text-[15px] font-semibold">1. Contract Details</h3>
        <p className="text-[13px] text-muted">Who signs for your company and the address for the contract.</p>
      </div>
      {message ? <Notice>{message}</Notice> : null}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="PIC Name" required error={errors.pic_name}>{(p) => <Input {...p} value={values.pic_name} onChange={set("pic_name")} autoComplete="name" />}</Field>
        <Field label="Tax ID (NPWP)" error={errors.tax_id}>{(p) => <Input {...p} value={values.tax_id} onChange={set("tax_id")} />}</Field>
        <Field label="Company Address" required className="sm:col-span-2" error={errors.company_address}>
          {(p) => <Textarea {...p} value={values.company_address} onChange={set("company_address")} autoComplete="street-address" />}
        </Field>
      </div>
      <Button type="submit" variant="primary" className="self-start" disabled={!dirty} loading={busy}>Save Details</Button>
    </form>
  );
}

function SignUpload({ leadId, contract: c, onSigned }: { leadId: string; contract: Contract; onSigned: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ready = Boolean(c.pic_name && c.company_address);

  const send = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("version", String(c.version));
    setBusy(true);
    setError(null);
    try {
      await upload(`/api/v1/portal/exhibitors/${leadId}/contract/signed-copy`, form);
      onSigned();
    } catch (err) {
      setError(err instanceof ApiError ? (Object.values(err.fields)[0] ?? err.message) : messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-6 flex flex-col gap-4 border-t border-line pt-6">
      <div>
        <h3 className="text-[15px] font-semibold">2. Signed Contract</h3>
        <p className="text-[13px] text-muted">
          Sign the contract your sales contact sent you and upload it as a PDF. After the upload the contract is final and can no longer be edited here.
        </p>
      </div>
      {!ready ? <Notice tone="amber">Save the PIC name and company address first.</Notice> : null}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field label="Signed PDF (up to 10 MB)" error={error ?? undefined} className="min-w-0 flex-1">
          {(p) => <Input {...p} type="file" accept="application/pdf,.pdf" disabled={!ready} className="py-2" onChange={(e) => { setError(null); setFile(e.target.files?.[0] ?? null); }} />}
        </Field>
        <Button variant="primary" disabled={!file || !ready} loading={busy} onClick={() => void send()}><FileUp aria-hidden />Upload Signed Contract</Button>
      </div>
    </div>
  );
}

function SignedCopy({ leadId }: { leadId: string }) {
  const [error, setError] = useState<string | null>(null);
  const download = async () => {
    try {
      setError(null);
      await downloadFile(`/api/v1/portal/exhibitors/${leadId}/contract/signed-copy`);
    } catch (e) {
      setError(messageOf(e));
    }
  };
  return (
    <div className="mt-5 flex flex-col items-start gap-3">
      {error ? <Notice>{error}</Notice> : null}
      <Button onClick={() => void download()}><Download aria-hidden />Download Signed Contract</Button>
    </div>
  );
}

function PaymentsPanel({ payments: p, signed }: { payments: Payments; signed: boolean }) {
  return (
    <Panel id="payments" title="Booth Payments" aside={signed ? <Status value={p.payment_state} /> : null}>
      {!signed ? (
        <p className="text-[14px] text-muted">Payments are shown here after the contract is signed.</p>
      ) : (
        <>
          <dl className="grid grid-cols-3 gap-4 max-sm:grid-cols-1">
            {[["Total", p.total_amount], ["Paid", p.verified_amount], ["Outstanding", p.outstanding_amount]].map(([k, v]) => (
              <div key={k}>
                <dt className="text-[12px] text-label">{k}</dt>
                <dd className="text-[20px] leading-7 font-semibold tabular-nums">{money(v, p.currency)}</dd>
              </div>
            ))}
          </dl>
          {Number(p.pending_amount) > 0 ? (
            <p className="mt-3 text-[13px] text-muted">{money(p.pending_amount, p.currency)} received and waiting for verification.</p>
          ) : null}
          {p.items.length === 0 ? (
            <p className="mt-5 text-[14px] text-muted">No payments recorded yet. After you pay, the organiser records the payment here.</p>
          ) : (
            <ul className="mt-5 divide-y divide-line border-t border-line">
              {p.items.map((x) => (
                <li key={x.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3 text-[14px]">
                  <span className="min-w-0">
                    <span className="block font-medium tabular-nums">{money(x.amount, p.currency)}</span>
                    <span className="block text-[13px] text-muted">
                      {date(x.paid_on)} · {label(x.method)}{x.reference ? ` · ${x.reference}` : ""}
                    </span>
                  </span>
                  <Status value={x.status} />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Panel>
  );
}

function doneForms(forms: Forms): number {
  return forms.forms.filter((f) => f.progress === "SUBMITTED" || f.progress === "APPROVED" || f.progress === "NOT_REQUIRED").length;
}

/** The exhibition at a glance: which show, when, and the booth (the identity motif). */
function Hero({ record }: { record: ExhibitorRecord }) {
  const when = showCountdown(record.edition_start_date, record.edition_end_date);
  return (
    <div className="flex items-start justify-between gap-5 rounded-[20px] bg-primary px-7 py-7 text-on-primary max-sm:px-5 max-sm:py-5">
      <div className="min-w-0">
        <p className="text-[14px] font-semibold text-hero-muted">{record.company_name}</p>
        <h1 className="mt-1 text-[30px] leading-tight font-extrabold max-sm:text-[24px]">{record.edition_name}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[14px]">
          <span className="font-semibold">{date(record.edition_start_date)} to {date(record.edition_end_date)}</span>
          <span className={when.live ? "rounded-full bg-accent px-3 py-1 text-[13px] font-bold" : "rounded-full bg-bg/15 px-3 py-1 text-[13px] font-semibold"}>{when.text}</span>
        </div>
      </div>
      <BoothTag code={record.booth_code} inverse />
    </div>
  );
}

type Step = { n: number; title: string; status: string; done: boolean; note: string; to: () => void };

/**
 * What the exhibitor has to do, in the real order: sign the contract, pay the booth, then order
 * services. Each step reads its own status; the next open step is the one highlighted.
 */
function Checklist({ leadId, contract, payments, forms }: { leadId: string; contract: Contract; payments: Payments; forms: Forms | null }) {
  const signed = contract.status === "SIGNED";
  const paid = signed && payments.payment_state === "PAID";
  const total = forms?.forms.length ?? 0;
  const done = forms ? doneForms(forms) : 0;
  const jump = (id: string) => () => document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  const steps: Step[] = [
    { n: 1, title: "Sign the contract", status: signed ? "Signed" : "To do", done: signed, note: signed ? `Signed ${date(contract.signed_at)}` : "Fill in the details and upload the signed PDF", to: jump("contract") },
    {
      n: 2,
      title: "Pay the booth",
      status: paid ? "Paid" : signed ? label(payments.payment_state) : "After signing",
      done: paid,
      note: signed ? `${money(payments.outstanding_amount, payments.currency)} still due` : "Opens once the contract is signed",
      to: jump("payments"),
    },
    {
      n: 3,
      title: "Order booth services",
      status: total ? `${done} of ${total}` : "None yet",
      done: total > 0 && done === total,
      note: total ? "Power, furniture, internet, badges and more" : "The organizer has not published forms yet",
      to: () => navigate(`/e/${leadId}/forms`),
    },
  ];
  const next = steps.find((s) => !s.done)?.n;
  return (
    <section aria-label="Your checklist" className="grid gap-3 md:grid-cols-3">
      {steps.map((s) => {
        const current = s.n === next;
        return (
          <button
            key={s.n}
            type="button"
            onClick={s.to}
            className={
              current
                ? "flex flex-col gap-2 rounded-[16px] border-2 border-primary bg-bg px-5 py-4 text-left transition-colors hover:bg-primary-soft"
                : "flex flex-col gap-2 rounded-[16px] border border-line bg-bg px-5 py-4 text-left transition-colors hover:border-primary/40"
            }
          >
            <span className="flex items-center justify-between gap-3">
              <span
                className={
                  s.done
                    ? "flex size-8 items-center justify-center rounded-full bg-[var(--green-bg)] text-[var(--green-fg)]"
                    : current
                      ? "flex size-8 items-center justify-center rounded-full bg-primary font-display text-[15px] font-bold text-on-primary"
                      : "flex size-8 items-center justify-center rounded-full bg-primary-soft font-display text-[15px] font-bold text-primary"
                }
              >
                {s.done ? <Check className="size-[18px]" aria-label="Done" /> : s.n}
              </span>
              <span className={s.done ? "text-[13px] font-semibold text-[var(--green-fg)]" : current ? "text-[13px] font-bold text-accent-ink" : "text-[13px] font-semibold text-label"}>
                {current ? "Next step" : s.status}
              </span>
            </span>
            <span className="font-display text-[17px] font-bold text-ink">{s.title}</span>
            <span className="text-[14px] text-muted">{s.note}</span>
          </button>
        );
      })}
    </section>
  );
}
