import { api, ApiError, call, downloadFile, type Schemas, upload } from "@ems/api";
import { ChevronLeft, Download, FileUp } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";

import { date, type ExhibitorRecord, href, label, messageOf, money, navigate } from "../lib";
import { Button, Facts, Field, Input, Notice, Panel, Status, Textarea } from "../ui";

type Contract = Schemas["ContractOut"];
type Payments = Schemas["PortalPaymentsOut"];
type Loaded = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; contract: Contract; payments: Payments };

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
      ])
        .then(([contract, payments]) => {
          setState({ kind: "ready", contract, payments });
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
        <a href={href("/")} onClick={(e) => { e.preventDefault(); navigate("/"); }} className="mb-2 inline-flex items-center gap-1 rounded-[6px] text-[13px] text-label hover:text-ink">
          <ChevronLeft className="size-4" aria-hidden />My Exhibitions
        </a>
        <h1 className="text-[24px] leading-8 font-semibold tracking-[-0.01em]">{record.edition_name}</h1>
        <p className="text-[14px] text-muted">
          {date(record.edition_start_date)} to {date(record.edition_end_date)} · {record.company_name}
        </p>
      </div>
      {state.kind === "loading" ? (
        <p role="status" className="py-10 text-center text-label">Loading</p>
      ) : state.kind === "error" ? (
        <div className="flex flex-col items-start gap-3"><Notice>{state.message}</Notice><Button onClick={() => load()}>Retry</Button></div>
      ) : (
        <>
          <ContractPanel
            key={state.contract.version}
            leadId={id}
            contract={state.contract}
            flash={flash}
            onChange={load}
            onError={failed}
          />
          <PaymentsPanel payments={state.payments} signed={state.contract.status === "SIGNED"} />
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
    <Panel title={`Contract ${c.contract_number ?? ""}`} aside={<Status value={c.status} />}>
      {flash ? <div className="mb-5"><Notice tone="green">{flash}</Notice></div> : null}
      <Facts
        items={[
          ["Booth", c.booth_code],
          ["Booth Price", money(c.booth_price, c.currency)],
          ...(Number(c.discount_amount) > 0 ? ([["Discount", money(c.discount_amount, c.currency)]] as [string, string][]) : []),
          ["Total", <span key="t" className="font-semibold">{money(c.total_amount, c.currency)}</span>],
          ...(signed ? ([["Signed", date(c.signed_at)], ["PIC", c.pic_name], ["Address", c.company_address], ["Tax ID (NPWP)", c.tax_id]] as [string, string | null][]) : []),
        ]}
      />
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
    <Panel title="Payments" aside={signed ? <Status value={p.payment_state} /> : null}>
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
