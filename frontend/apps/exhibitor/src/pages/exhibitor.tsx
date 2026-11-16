import { api, ApiError, call, downloadFile, type Schemas, upload } from "@ems/api";
import { CalendarDays, ChevronRight, CircleCheck, Download, FileUp, House, NotebookPen, ClipboardList } from "lucide-react";
import { type FormEvent, type ReactNode, useCallback, useEffect, useState } from "react";

import { date, dayParts, type ExhibitorRecord, formCounts, href, label, messageOf, money, navigate, showCountdown } from "../lib";
import { Button, Facts, Field, Input, Notice, PageBody, PageHead, Panel, Progress, Status, Textarea } from "../ui";

type Contract = Schemas["ContractOut"];
type Payments = Schemas["PortalPaymentsOut"];
type Forms = Schemas["PortalOrderFormsOut"];
type Loaded = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; contract: Contract; payments: Payments; forms: Forms | null };

/** Contract, payments, and order forms of one exhibitor, with a 401 handing the session back. */
function useExhibitor(id: string, onSignedOut: () => void) {
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
        // The home still shows without the order forms if they fail to load.
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
  return { state, flash, load, failed };
}

function link(to: string) {
  return { href: href(to), onClick: (e: { preventDefault: () => void }) => { e.preventDefault(); navigate(to); } };
}

/**
 * The exhibition home, laid out as the old manual's: a band with the show, a welcome with the next
 * step, links to the contract and payments, the order forms at a glance, and the show date.
 */
export function ExhibitorPage({ record, onSignedOut }: { record: ExhibitorRecord; onSignedOut: () => void }) {
  const id = record.exhibitor_lead_id;
  const { state, load } = useExhibitor(id, onSignedOut);
  return (
    <PageBody>
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-[12px] bg-primary px-7 py-6 text-on-primary max-sm:px-5">
        <p className="text-[26px] leading-tight font-extrabold max-sm:text-[22px]">{record.edition_name}</p>
        <p className="text-[15px] font-semibold">{date(record.edition_start_date)} to {date(record.edition_end_date)}{record.venue_name ? ` · ${record.venue_name}` : ""}</p>
      </div>
      {state.kind === "loading" ? (
        <p role="status" className="py-10 text-center text-label">Loading</p>
      ) : state.kind === "error" ? (
        <div className="flex flex-col items-start gap-3"><Notice>{state.message}</Notice><Button onClick={() => load()}>Retry</Button></div>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,3.5fr)_minmax(150px,1.2fr)]">
          <div className="flex flex-col gap-6">
            <Welcome record={record} contract={state.contract} payments={state.payments} forms={state.forms} />
            <section aria-label="Contract and payments" className="flex flex-col gap-6 rounded-[12px] border border-line bg-bg px-6 py-6 max-sm:px-4">
              <HomeLink to={`/e/${id}/contract`} title="Contract" aside={<Status value={state.contract.status} />}>
                {state.contract.status === "SIGNED"
                  ? `Contract ${state.contract.contract_number ?? ""} is signed. Download your copy or see the terms of payment.`
                  : "Fill in who signs for your company, then upload the signed contract as a PDF."}
              </HomeLink>
              <HomeLink to={`/e/${id}/contract#payments`} title="Booth Payments" aside={state.contract.status === "SIGNED" ? <Status value={state.payments.payment_state} /> : null}>
                {state.contract.status === "SIGNED"
                  ? `${money(state.payments.outstanding_amount, state.payments.currency)} still to pay of ${money(state.payments.total_amount, state.payments.currency)}.`
                  : "Your payments show here once the contract is signed."}
              </HomeLink>
            </section>
          </div>
          <FormsCard leadId={id} forms={state.forms} />
          <ShowDate record={record} />
        </div>
      )}
    </PageBody>
  );
}

function Welcome({ record, contract, payments, forms }: { record: ExhibitorRecord; contract: Contract; payments: Payments; forms: Forms | null }) {
  const signed = contract.status === "SIGNED";
  const counts = formCounts(forms?.forms ?? []);
  const total = forms?.forms.length ?? 0;
  const next = !signed
    ? "Next step: sign your booth contract."
    : payments.payment_state !== "PAID"
      ? "Next step: pay your booth."
      : total > counts.done
        ? "Next step: fill in your order forms."
        : "You are all set. See you at the show!";
  return (
    <section className="rounded-[12px] border border-line bg-bg px-6 py-6 max-sm:px-4">
      <House className="size-6 text-ink" aria-hidden />
      <h1 className="mt-3 text-[20px] font-bold text-ink">Welcome, {record.company_name}</h1>
      <p className="mt-2 text-[15px] text-muted">Booth: <span className="font-semibold text-ink">{record.booth_code ?? "not assigned yet"}</span></p>
      <p className="mt-3 text-[14px] text-label">We made every effort to keep your pre-show work simple. This manual guides you through your contract, payments, and the services for your booth.</p>
      <p className="mt-3 text-[14px] font-semibold text-primary">{next}</p>
    </section>
  );
}

function HomeLink({ to, title, aside, children }: { to: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <a {...link(to)} className="group flex flex-col gap-2 rounded-[8px]">
      <span className="flex items-center justify-between gap-3">
        <span className="flex flex-wrap items-center gap-3">
          <span className="text-[19px] font-bold text-primary group-hover:underline">{title}</span>
          {aside}
        </span>
        <ChevronRight className="size-5 shrink-0 text-ink" aria-hidden />
      </span>
      <span className="text-[15px] text-muted">{children}</span>
    </a>
  );
}

/** The old home's Order Forms card: progress, then how many are not filled, in progress, submitted. */
function FormsCard({ leadId, forms }: { leadId: string; forms: Forms | null }) {
  const list = forms?.forms ?? [];
  const counts = formCounts(list);
  const rows: [string, number, ReactNode, string][] = [
    ["Not Filled", counts.notFilled, <ClipboardList key="n" className="size-4" aria-hidden />, "var(--red-fg)"],
    ["In Progress", counts.inProgress, <NotebookPen key="p" className="size-4" aria-hidden />, "#c2410c"],
    ["Submitted", counts.sent, <CircleCheck key="s" className="size-4" aria-hidden />, "var(--green-fg)"],
  ];
  return (
    <section className="rounded-[12px] border border-line bg-bg px-6 py-6 max-sm:px-4">
      <a {...link(`/e/${leadId}/forms`)} className="group flex items-center justify-between gap-3 rounded-[8px]">
        <h2 className="text-[19px] font-bold text-primary group-hover:underline">Order Forms</h2>
        <ChevronRight className="size-5 text-ink" aria-hidden />
      </a>
      {list.length === 0 ? (
        <p className="mt-4 text-[14px] text-muted">The organizer has not published any order forms yet.</p>
      ) : (
        <>
          <div className="mt-4"><Progress done={counts.done} total={list.length} label="Order forms done" /></div>
          <ul className="mt-4 divide-y divide-line">
            {rows.map(([text, n, icon, color]) => (
              <li key={text} className="flex items-center justify-between gap-3 py-3.5">
                <span className="flex items-center gap-3 text-[15px]">
                  <span className="flex size-7 items-center justify-center rounded-full text-white" style={{ background: color }}>{icon}</span>
                  {text}
                </span>
                <span className="text-[16px] font-bold tabular-nums">{n}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

function ShowDate({ record }: { record: ExhibitorRecord }) {
  const start = dayParts(record.edition_start_date);
  const when = showCountdown(record.edition_start_date, record.edition_end_date);
  return (
    <section aria-label="Show date" className="rounded-[12px] border border-line bg-bg px-5 py-6 text-center">
      <p className="flex items-center justify-center gap-2 text-[14px] text-muted"><CalendarDays className="size-4" aria-hidden />Expo date</p>
      <p className="mt-2 text-[22px] leading-none font-bold text-primary">{start.day}</p>
      <p className="mt-1.5 text-[20px] font-semibold text-ink">{start.month}</p>
      <p className="mt-4 border-t border-line pt-4 text-[14px] text-muted">{when.text}</p>
    </section>
  );
}

/** Contract and booth payments, on their own page as in the old manual's menu. */
export function ContractPage({ record, onSignedOut }: { record: ExhibitorRecord; onSignedOut: () => void }) {
  const id = record.exhibitor_lead_id;
  const { state, flash, load, failed } = useExhibitor(id, onSignedOut);
  // "#payments" from the home card: scroll once the panels are there.
  useEffect(() => {
    if (state.kind === "ready" && location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
  }, [state.kind]);
  return (
    <>
      <PageHead title="Contract & Payments" subtitle={`${record.company_name} · Booth ${record.booth_code ?? "not assigned yet"} · ${record.edition_name}`} />
      <PageBody className="max-w-[1080px]">
        {state.kind === "loading" ? (
          <p role="status" className="py-10 text-center text-label">Loading</p>
        ) : state.kind === "error" ? (
          <div className="flex flex-col items-start gap-3"><Notice>{state.message}</Notice><Button onClick={() => load()}>Retry</Button></div>
        ) : (
          <>
            <ContractPanel key={state.contract.version} leadId={id} contract={state.contract} flash={flash} onChange={load} onError={failed} />
            <PaymentsPanel payments={state.payments} signed={state.contract.status === "SIGNED"} />
          </>
        )}
      </PageBody>
    </>
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
