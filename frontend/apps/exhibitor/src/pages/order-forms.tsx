import { api, ApiError, call, downloadFile, type Schemas, upload } from "@ems/api";
import { ChevronLeft, ChevronRight, Download, ImageUp, Plus, Send, Trash2 } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { date, type ExhibitorRecord, href, label, messageOf, money, navigate, timeLeft } from "../lib";
import { Button, Facts, Field, Input, Notice, Panel, Status, Textarea } from "../ui";

type FormsList = Schemas["PortalOrderFormsOut"];
type FormRow = Schemas["PortalOrderFormOut"];
type Detail = Schemas["PortalOrderFormDetailOut"];
type Order = Schemas["PortalOrderOut"];
type Item = Schemas["PortalCatalogItemOut"];
type Purpose = Detail["attachment_purposes"][number];

const PURPOSES: Record<Purpose, { label: string; accept: string; help: string }> = {
  LOGO: { label: "Logo", accept: ".jpg,.jpeg,.png,image/jpeg,image/png", help: "JPG or PNG, up to 10 MB." },
  PRODUCT_IMAGE: { label: "Product Images", accept: ".jpg,.jpeg,.png,image/jpeg,image/png", help: "JPG or PNG, up to 10 MB each." },
  FITTING_LOCATION: { label: "Fitting Location", accept: ".pdf,.jpg,.jpeg,.png", help: "Your booth layout with the points marked. PDF, JPG, or PNG, up to 10 MB." },
  VISA_LIST: { label: "Visa List", accept: ".xlsx,.pdf", help: "Excel or PDF, up to 10 MB." },
  OTHER: { label: "Other File", accept: ".pdf,.xlsx,.jpg,.jpeg,.png", help: "PDF, Excel, JPG, or PNG, up to 10 MB." },
};

// A confirmation carried to the next page (after sending, the form page shows it).
let pendingFlash: string | null = null;
function takeFlash(): string | null {
  const message = pendingFlash;
  pendingFlash = null;
  return message;
}

type Load<T> = { kind: "loading" } | { kind: "error"; message: string } | { kind: "ready"; data: T };

/** GET with loading and error states; a 401 hands the session back to the app. */
function useLoad<T>(fetcher: () => Promise<T>, onSignedOut: () => void): [Load<T>, () => Promise<void>] {
  const [state, setState] = useState<Load<T>>({ kind: "loading" });
  const reload = useCallback(
    () =>
      fetcher()
        .then((data) => setState({ kind: "ready", data }))
        .catch((e: unknown) => {
          if (e instanceof ApiError && e.status === 401) onSignedOut();
          else setState({ kind: "error", message: messageOf(e) });
        }),
    [fetcher, onSignedOut],
  );
  useEffect(() => {
    void reload();
  }, [reload]);
  return [state, reload];
}

function Back({ to, children }: { to: string; children: ReactNode }) {
  return (
    <a href={href(to)} onClick={(e) => { e.preventDefault(); navigate(to); }} className="mb-2 inline-flex items-center gap-1 rounded-[6px] text-[13px] text-label hover:text-ink">
      <ChevronLeft className="size-4" aria-hidden />{children}
    </a>
  );
}

function Loading() {
  return <p role="status" className="py-10 text-center text-label">Loading</p>;
}

function Failed({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="flex flex-col items-start gap-3"><Notice>{message}</Notice><Button onClick={onRetry}>Retry</Button></div>;
}

function deadlineText(f: { deadline_on?: string | null; is_closed: boolean; closes_on?: string | null }): string {
  if (f.is_closed) return `Closed ${date(f.closes_on)}`;
  if (!f.deadline_on) return f.closes_on ? `Open until ${date(f.closes_on)}` : "No deadline";
  return `Deadline ${date(f.deadline_on)} · ${timeLeft(f.deadline_on)}`;
}

function periodNotice(period: Detail["price_period"]): ReactNode {
  if (period === null) return <Notice tone="amber">Ordering is not open today. Prices shown are the regular prices; you can prepare a draft and send it once ordering opens.</Notice>;
  if (period === "SURCHARGE" || period === "ONSITE") return <Notice tone="amber">{label(period)}s apply today.</Notice>;
  return null;
}

// --- list --------------------------------------------------------------------------------

const FILTERS = [
  ["all", "All Forms"],
  ["todo", "Not Filled"],
  ["progress", "In Progress"],
  ["sent", "Sent"],
] as const;
type Filter = (typeof FILTERS)[number][0];

function matches(f: FormRow, filter: Filter): boolean {
  if (filter === "todo") return f.progress === "NOT_STARTED";
  if (filter === "progress") return f.progress === "IN_PROGRESS";
  if (filter === "sent") return f.progress === "SUBMITTED" || f.progress === "APPROVED";
  return true;
}

export function OrderFormsPage({ record, onSignedOut }: { record: ExhibitorRecord; onSignedOut: () => void }) {
  const id = record.exhibitor_lead_id;
  const fetcher = useCallback(() => call(api.GET("/api/v1/portal/exhibitors/{lead_id}/order-forms", { params: { path: { lead_id: id } } })), [id]);
  const [state, reload] = useLoad<FormsList>(fetcher, onSignedOut);
  const [filter, setFilter] = useState<Filter>("all");
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Back to={`/e/${id}`}>{record.edition_name}</Back>
        <h1 className="text-[24px] leading-8 font-semibold tracking-[-0.01em]">Order Forms</h1>
        <p className="text-[14px] text-muted">Services for booth {record.booth_code ?? ""}: electricity, furniture, internet, badges, and more.</p>
      </div>
      {state.kind === "loading" ? <Loading /> : state.kind === "error" ? <Failed message={state.message} onRetry={() => void reload()} /> : (
        <>
          {periodNotice(state.data.price_period)}
          <FormsPanel forms={state.data.forms} leadId={id} filter={filter} onFilter={setFilter} />
        </>
      )}
    </div>
  );
}

function FormsPanel({ forms, leadId, filter, onFilter }: { forms: FormRow[]; leadId: string; filter: Filter; onFilter: (f: Filter) => void }) {
  const done = forms.filter((f) => f.progress === "SUBMITTED" || f.progress === "APPROVED" || f.progress === "NOT_REQUIRED").length;
  const shown = forms.filter((f) => matches(f, filter));
  if (forms.length === 0) {
    return <Panel><p className="text-[14px] text-muted">The organizer has not published any order forms yet.</p></Panel>;
  }
  return (
    <Panel title={`${done} of ${forms.length} done`} aside={
      <div role="group" aria-label="Show" className="flex flex-wrap gap-1">
        {FILTERS.map(([value, text]) => (
          <button key={value} type="button" aria-pressed={filter === value} onClick={() => onFilter(value)}
            className={`h-8 rounded-[8px] px-3 text-[13px] ${filter === value ? "bg-primary text-on-primary" : "bg-input hover:bg-hover"}`}>
            {text}
          </button>
        ))}
      </div>
    }>
      {shown.length === 0 ? <p className="text-[14px] text-muted">No forms match.</p> : (
        <ul className="-my-2 divide-y divide-line">
          {shown.map((f) => (
            <li key={f.code}>
              <a href={href(`/e/${leadId}/forms/${f.code}`)} onClick={(e) => { e.preventDefault(); navigate(`/e/${leadId}/forms/${f.code}`); }}
                className="flex items-center gap-3 rounded-[8px] py-3 hover:bg-hover">
                <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-input text-[12px] font-medium tabular-nums">{f.code}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium">{f.title}</span>
                  <span className={`block text-[12px] ${f.is_closed ? "text-label" : timeLeft(f.deadline_on) === "Past" ? "text-required" : "text-label"}`}>{deadlineText(f)}</span>
                </span>
                <Status value={f.progress} />
                <ChevronRight className="size-4 shrink-0 text-label" aria-hidden />
              </a>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// --- form --------------------------------------------------------------------------------

interface Draft {
  quantities: Record<string, string>; // item id -> typed quantity
  custom: { key: string; id: string | null; name: string; size: string; quantity: string; notes: string; hasImage: boolean }[];
  remarks: string;
}

function draftOf(order: Order | null | undefined): Draft {
  const quantities: Record<string, string> = {};
  const custom: Draft["custom"] = [];
  for (const line of order?.lines ?? []) {
    if (line.item_id) quantities[line.item_id] = String(line.quantity);
    else custom.push({ key: line.id, id: line.id, name: line.name, size: line.size ?? "", quantity: String(line.quantity), notes: line.notes ?? "", hasImage: line.has_image });
  }
  return { quantities, custom, remarks: order?.remarks ?? "" };
}

function bodyOf(d: Draft, items: Item[]) {
  return {
    lines: items.filter((i) => Number(d.quantities[i.id] ?? 0) > 0).map((i) => ({ item_id: i.id, quantity: Number(d.quantities[i.id]) })),
    custom_lines: d.custom.filter((c) => c.name.trim()).map((c) => ({ id: c.id, name: c.name, size: c.size || null, quantity: Number(c.quantity) || 1, notes: c.notes || null })),
    remarks: d.remarks || null,
  };
}

function sameDraft(a: Draft, b: Draft, items: Item[]): boolean {
  return JSON.stringify(bodyOf(a, items)) === JSON.stringify(bodyOf(b, items));
}

export function OrderFormPage({ record, code, onSignedOut }: { record: ExhibitorRecord; code: string; onSignedOut: () => void }) {
  const id = record.exhibitor_lead_id;
  const fetcher = useCallback(() => call(api.GET("/api/v1/portal/exhibitors/{lead_id}/order-forms/{code}", { params: { path: { lead_id: id, code } } })), [id, code]);
  const [state, reload] = useLoad<Detail>(fetcher, onSignedOut);
  return (
    <div className="flex flex-col gap-6">
      {state.kind === "loading" ? <Loading /> : state.kind === "error" ? (
        <><Back to={`/e/${id}/forms`}>Order Forms</Back><Failed message={state.message} onRetry={() => void reload()} /></>
      ) : (
        <FormEditor key={`${state.data.open_order?.id ?? "new"}-${state.data.open_order?.version ?? 0}-${state.data.sent_orders.length}-${String(state.data.not_required)}`} leadId={id} detail={state.data} onReload={reload} onSignedOut={onSignedOut} />
      )}
    </div>
  );
}

function FormEditor({ leadId, detail: d, onReload, onSignedOut }: { leadId: string; detail: Detail; onReload: () => Promise<void>; onSignedOut: () => void }) {
  const open = d.open_order ?? null;
  const saved = useMemo(() => draftOf(open), [open]);
  const [draft, setDraft] = useState<Draft>(saved);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // The editor remounts after every save (its key follows the order), so it picks up the confirmation.
  const [message, setMessage] = useState<{ tone: "red" | "green"; text: string } | null>(() => {
    const flash = takeFlash();
    return flash ? { tone: "green", text: flash } : null;
  });
  const [busy, setBusy] = useState<string | null>(null);
  const editable = !d.is_closed && (open === null || open.status === "DRAFT" || open.status === "RETURNED");
  // After an order is sent the form shows it, and a new order starts only when asked for.
  const [adding, setAdding] = useState(false);
  const showEditor = open !== null || d.sent_orders.length === 0 || adding;
  const dirty = !sameDraft(draft, saved, d.items);
  const total = d.items.reduce((sum, i) => sum + Number(draft.quantities[i.id] ?? 0) * Number(i.unit_price), 0);
  const base = `/api/v1/portal/exhibitors/${leadId}`;

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.status === 401) return onSignedOut();
    if (e instanceof ApiError) setErrors(e.fields);
    setMessage({ tone: "red", text: messageOf(e) });
  };

  // A draft created by a save whose lines were then refused: reuse it on the next try.
  const created = useRef<Order | null>(null);
  /** The open order, created on first save or upload. */
  const ensureOrder = async (): Promise<Order> => {
    const existing = open ?? created.current;
    if (existing) return existing;
    created.current = await call(api.POST("/api/v1/portal/exhibitors/{lead_id}/order-forms/{code}/orders", { params: { path: { lead_id: leadId, code: d.code } } }));
    return created.current;
  };

  const save = async (): Promise<Order | null> => {
    const order = await ensureOrder();
    return await call(
      api.PATCH("/api/v1/portal/exhibitors/{lead_id}/orders/{order_id}", {
        params: { path: { lead_id: leadId, order_id: order.id } },
        body: { ...bodyOf(draft, d.items), version: order.version },
      }),
    );
  };

  const run = async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    setErrors({});
    setMessage(null);
    try {
      await action();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const saveDraft = () => run("save", async () => {
    await save();
    pendingFlash = "Draft saved. Nothing is sent until you choose Review and Send.";
    await onReload();
  });
  const review = () => run("review", async () => {
    if (dirty || !open) await save();
    navigate(`/e/${leadId}/forms/${d.code}/review`);
  });
  const discard = () => run("delete", async () => {
    if (!open) return;
    await call(api.DELETE("/api/v1/portal/exhibitors/{lead_id}/orders/{order_id}", { params: { path: { lead_id: leadId, order_id: open.id } } }));
    pendingFlash = "Draft deleted.";
    await onReload();
  });
  const notRequired = (value: boolean) => run("waive", async () => {
    const path = { params: { path: { lead_id: leadId, code: d.code } } };
    if (value) await call(api.PUT("/api/v1/portal/exhibitors/{lead_id}/order-forms/{code}/not-required", path));
    else await call(api.DELETE("/api/v1/portal/exhibitors/{lead_id}/order-forms/{code}/not-required", path));
    await onReload();
  });
  const uploadTo = (name: string, path: string, form: FormData) => run(name, async () => {
    const order = await ensureOrder();
    if (dirty) await save();
    const fresh = dirty ? (await call(api.GET("/api/v1/portal/exhibitors/{lead_id}/order-forms/{code}", { params: { path: { lead_id: leadId, code: d.code } } }))).open_order : order;
    form.append("version", String(fresh?.version ?? order.version));
    await upload<Order>(`${base}/orders/${order.id}${path}`, form);
    pendingFlash = "File received.";
    await onReload();
  });

  const sections = useMemo(() => {
    const groups = new Map<string, Item[]>();
    for (const i of d.items) groups.set(i.section ?? "", [...(groups.get(i.section ?? "") ?? []), i]);
    return [...groups.entries()];
  }, [d.items]);

  return (
    <>
      <div>
        <Back to={`/e/${leadId}/forms`}>Order Forms</Back>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-[24px] leading-8 font-semibold tracking-[-0.01em]">{d.code} · {d.title}</h1>
          <Status value={d.progress} />
        </div>
        <p className="text-[14px] text-muted">
          {deadlineText(d)}
          {d.secondary_deadline_label && d.secondary_deadline_on ? ` · ${d.secondary_deadline_label} ${date(d.secondary_deadline_on)}` : ""}
        </p>
      </div>
      {message ? <Notice tone={message.tone}>{message.text}</Notice> : null}
      {d.is_closed ? <Notice tone="amber">This form closed on {date(d.closes_on)}. Contact the organizer if you still need something.</Notice> : periodNotice(d.price_period)}
      {open?.status === "RETURNED" ? (
        <Notice tone="amber">The organizer sent order {open.order_number} back: {open.review_notes}. Change it below and send it again.</Notice>
      ) : null}

      <Panel title="Company">
        <Facts items={[["Company", d.company_name], ["Booth", d.booth_code]]} />
      </Panel>
      {d.instructions ? <Panel title="Notes"><p className="text-[14px] whitespace-pre-line">{d.instructions}</p></Panel> : null}

      {showEditor ? (
        <>
        {d.has_catalog ? (
          <Panel title="Items" aside={<span className="text-[14px] font-semibold tabular-nums">Total {money(String(total), d.currency)}</span>}>
            {d.items.length === 0 ? <p className="text-[14px] text-muted">No items yet.</p> : sections.map(([section, items]) => (
              <div key={section} className="mb-6 last:mb-0">
                {section ? <h3 className="mb-2 text-[14px] font-semibold">{section}</h3> : null}
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] text-[14px]">
                    <caption className="sr-only">{section || "Items"}</caption>
                    <thead>
                      <tr className="border-b border-line text-left text-[12px] text-label">
                        <th scope="col" className="py-2 pr-3 font-normal">Item</th>
                        <th scope="col" className="py-2 pr-3 text-right font-normal">Price</th>
                        <th scope="col" className="w-24 py-2 pr-3 text-right font-normal">Quantity</th>
                        <th scope="col" className="py-2 text-right font-normal">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((i) => {
                        const qty = Number(draft.quantities[i.id] ?? 0);
                        const error = errors[`lines.${i.id}`];
                        return (
                          <tr key={i.id} className="border-b border-line align-top last:border-0">
                            <td className="py-2.5 pr-3">
                              <div className="flex items-start gap-3">
                                {i.has_image ? <img src={`${base}/order-forms/${d.code}/items/${i.id}/image`} alt="" className="size-12 shrink-0 rounded-[6px] border border-line object-contain" /> : null}
                                <div className="min-w-0">
                                  <div className="font-medium">{i.name}</div>
                                  <div className="text-[12px] text-label">{[i.code, i.size, i.unit].filter(Boolean).join(" · ")}</div>
                                  {i.description ? <div className="text-[12px] text-muted">{i.description}</div> : null}
                                  {error ? <div className="text-[12px] text-required">{error}</div> : null}
                                </div>
                              </div>
                            </td>
                            <td className="py-2.5 pr-3 text-right tabular-nums">{money(i.unit_price, d.currency)}</td>
                            <td className="py-2.5 pr-3 text-right">
                              <Input aria-label={`Quantity of ${i.name}`} aria-invalid={Boolean(error)} inputMode="numeric" disabled={!editable} className="h-9 w-20 text-right tabular-nums"
                                value={draft.quantities[i.id] ?? ""} placeholder="0"
                                onChange={(e) => {
                                  const v = e.target.value.replace(/\D/g, "").slice(0, 4);
                                  setDraft((s) => ({ ...s, quantities: { ...s.quantities, [i.id]: v } }));
                                }} />
                              {i.max_quantity ? <div className="mt-1 text-[11px] text-label">Up to {i.max_quantity}</div> : null}
                            </td>
                            <td className="py-2.5 text-right tabular-nums">{qty > 0 ? money(String(qty * Number(i.unit_price)), d.currency) : ""}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </Panel>
        ) : null}

        {d.allow_custom_items ? (
          <Panel title="Extra Items" aside={editable ? (
            <Button type="button" variant="ghost" className="h-9" onClick={() => setDraft((s) => ({ ...s, custom: [...s.custom, { key: crypto.randomUUID(), id: null, name: "", size: "", quantity: "1", notes: "", hasImage: false }] }))}>
              <Plus aria-hidden />Add Extra Item
            </Button>
          ) : null}>
            <p className="mb-4 text-[13px] text-muted">Something not in the list? Describe it here. The organizer sets the price and confirms it with your order.</p>
            {errors.custom_lines ? <p className="mb-3 text-[12px] text-required">{errors.custom_lines}</p> : null}
            {draft.custom.length === 0 ? <p className="text-[14px] text-label">No extra items.</p> : (
              <div className="flex flex-col gap-4">
                {draft.custom.map((c, n) => {
                  const set = (patch: Partial<Draft["custom"][number]>) => setDraft((s) => ({ ...s, custom: s.custom.map((x) => (x.key === c.key ? { ...x, ...patch } : x)) }));
                  return (
                    <div key={c.key} className="grid grid-cols-1 gap-3 rounded-[8px] border border-line p-3 sm:grid-cols-[2fr_1fr_90px_auto]">
                      <Field label={`Extra item ${n + 1}`}>{(p) => <Input {...p} disabled={!editable} value={c.name} maxLength={300} onChange={(e) => set({ name: e.target.value })} />}</Field>
                      <Field label="Size">{(p) => <Input {...p} disabled={!editable} value={c.size} maxLength={100} onChange={(e) => set({ size: e.target.value })} />}</Field>
                      <Field label="Quantity">{(p) => <Input {...p} disabled={!editable} inputMode="numeric" value={c.quantity} onChange={(e) => set({ quantity: e.target.value.replace(/\D/g, "").slice(0, 4) })} />}</Field>
                      <div className="flex items-end">
                        {editable ? <Button type="button" variant="ghost" className="h-10" aria-label={`Remove extra item ${n + 1}`} onClick={() => setDraft((s) => ({ ...s, custom: s.custom.filter((x) => x.key !== c.key) }))}><Trash2 aria-hidden /></Button> : null}
                      </div>
                      <Field label="Notes" className="sm:col-span-3">{(p) => <Input {...p} disabled={!editable} value={c.notes} maxLength={500} onChange={(e) => set({ notes: e.target.value })} />}</Field>
                      {c.id && editable ? (
                        <LinePicture hasImage={c.hasImage} src={open ? `${base}/orders/${open.id}/lines/${c.id}/image?v=${open.version}` : null} busy={busy === `line-${c.id}`}
                          onUpload={(file) => { const f = new FormData(); f.append("file", file); void uploadTo(`line-${c.id}`, `/lines/${c.id}/image`, f); }} />
                      ) : c.id === null && editable ? <p className="self-end text-[12px] text-label sm:col-span-4">Save the draft to add a picture.</p> : null}
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        ) : null}

        {d.attachment_purposes.length ? (
          <Panel title="Attachments">
            <div className="flex flex-col gap-5">
              {d.attachment_purposes.map((purpose) => (
                <Attachment key={purpose} purpose={purpose} files={(open?.files ?? []).filter((f) => f.purpose === purpose)} editable={editable} busy={busy === purpose} error={busy === null ? errors.file ?? errors.purpose : undefined}
                  onUpload={(file) => { const f = new FormData(); f.append("file", file); f.append("purpose", purpose); void uploadTo(purpose, "/files", f); }}
                  onRemove={(fileId) => run(`remove-${fileId}`, async () => {
                    if (!open) return;
                    await call(api.DELETE("/api/v1/portal/exhibitors/{lead_id}/orders/{order_id}/files/{file_id}", { params: { path: { lead_id: leadId, order_id: open.id, file_id: fileId }, query: { version: open.version } } }));
                    await onReload();
                  })}
                  onDownload={(fileId, name) => void downloadFile(`${base}/orders/${open?.id ?? ""}/files/${fileId}`, name).catch(fail)} />
              ))}
            </div>
          </Panel>
        ) : null}

        {editable ? (
          <Panel>
            <div className="flex flex-col gap-5">
              <Field label="Remarks" help="Anything the organizer should know about this order.">
                {(p) => <Textarea {...p} value={draft.remarks} maxLength={2000} onChange={(e) => setDraft((s) => ({ ...s, remarks: e.target.value }))} />}
              </Field>
              <div className="flex flex-wrap items-center justify-between gap-3">
                {d.sent_orders.some((o) => o.status === "SUBMITTED" || o.status === "APPROVED") ? <span /> : (
                  <label className="flex items-center gap-2 text-[14px]">
                    <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={d.not_required} disabled={busy !== null} onChange={(e) => void notRequired(e.target.checked)} />
                    I don't require this form
                  </label>
                )}
                <div className="flex flex-wrap gap-2">
                  {open?.status === "DRAFT" ? <Button type="button" variant="ghost" loading={busy === "delete"} onClick={() => void discard()}>Delete Draft</Button> : null}
                  <Button type="button" disabled={!dirty} loading={busy === "save"} onClick={() => void saveDraft()}>Save Draft</Button>
                  <Button type="button" variant="primary" loading={busy === "review"} onClick={() => void review()}>Review and Send<ChevronRight aria-hidden /></Button>
                </div>
              </div>
            </div>
          </Panel>
        ) : null}

        </>
      ) : editable ? (
        <Panel>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[14px] text-muted">Need more on this form? Start another order; the sent ones stay as they are.</p>
            <Button type="button" variant="primary" onClick={() => setAdding(true)}><Plus aria-hidden />Order More</Button>
          </div>
        </Panel>
      ) : null}
      {d.sent_orders.length ? <SentOrders orders={d.sent_orders} /> : null}
    </>
  );
}

function LinePicture({ hasImage, src, busy, onUpload }: { hasImage: boolean; src: string | null; busy: boolean; onUpload: (file: File) => void }) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <div className="flex flex-wrap items-end gap-3 sm:col-span-4">
      {hasImage && src ? <img src={src} alt="" className="size-14 rounded-[6px] border border-line object-contain" /> : null}
      <Field label={hasImage ? "Replace Picture" : "Picture"} help="JPG or PNG, up to 5 MB.">
        {(p) => <Input {...p} type="file" accept=".jpg,.jpeg,.png,image/jpeg,image/png" className="py-2" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
      </Field>
      <Button type="button" disabled={!file} loading={busy} onClick={() => file && onUpload(file)}><ImageUp aria-hidden />Upload</Button>
    </div>
  );
}

function Attachment({ purpose, files, editable, busy, error, onUpload, onRemove, onDownload }: {
  purpose: Purpose;
  files: Order["files"];
  editable: boolean;
  busy: boolean;
  error: string | undefined;
  onUpload: (file: File) => void;
  onRemove: (id: string) => void;
  onDownload: (id: string, name: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const info = PURPOSES[purpose];
  return (
    <div>
      <h3 className="mb-2 text-[14px] font-semibold">{info.label}</h3>
      {files.length ? (
        <ul className="mb-3 flex flex-col gap-1">
          {files.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-2 text-[14px]">
              <button type="button" className="inline-flex items-center gap-1 text-link hover:underline" onClick={() => onDownload(f.id, f.file_name)}><Download className="size-4" aria-hidden />{f.file_name}</button>
              {editable ? <Button type="button" variant="ghost" className="h-8 px-2" aria-label={`Remove ${f.file_name}`} onClick={() => onRemove(f.id)}><Trash2 aria-hidden /></Button> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {editable ? (
        <div className="flex flex-wrap items-end gap-3">
          <Field label={`Add ${info.label}`} help={info.help} error={error}>
            {(p) => <Input {...p} type="file" accept={info.accept} className="py-2" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
          </Field>
          <Button type="button" disabled={!file} loading={busy} onClick={() => file && onUpload(file)}>Upload</Button>
        </div>
      ) : files.length === 0 ? <p className="text-[14px] text-label">None.</p> : null}
    </div>
  );
}

function LinesTable({ order }: { order: Order }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-[14px]">
        <caption className="sr-only">Items in order {order.order_number ?? ""}</caption>
        <thead>
          <tr className="border-b border-line text-left text-[12px] text-label">
            <th scope="col" className="py-2 pr-3 font-normal">Item</th>
            <th scope="col" className="py-2 pr-3 text-right font-normal">Price</th>
            <th scope="col" className="py-2 pr-3 text-right font-normal">Quantity</th>
            <th scope="col" className="py-2 text-right font-normal">Amount</th>
          </tr>
        </thead>
        <tbody>
          {order.lines.map((l) => (
            <tr key={l.id} className="border-b border-line last:border-0">
              <td className="py-2 pr-3">{l.name}{l.size ? <span className="text-label"> · {l.size}</span> : null}{l.item_id ? null : <span className="text-label"> (extra item)</span>}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{l.unit_price == null ? <span className="text-label">Set by the organizer</span> : money(l.unit_price, order.currency)}</td>
              <td className="py-2 pr-3 text-right tabular-nums">{l.quantity}</td>
              <td className="py-2 text-right tabular-nums">{l.amount == null ? "" : money(l.amount, order.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SentOrders({ orders }: { orders: Order[] }) {
  return (
    <Panel title="Sent Orders">
      <div className="flex flex-col gap-6">
        {orders.map((o) => (
          <div key={o.id}>
            <div className="mb-2 flex flex-wrap items-center gap-3">
              <h3 className="text-[15px] font-semibold">Order {o.order_number}</h3>
              <Status value={o.status} />
              <span className="text-[13px] text-label">Sent {date(o.submitted_at)} · {label(o.price_period)}</span>
            </div>
            {o.waiting_for_contract ? <div className="mb-2"><Notice tone="amber">The organizer confirms this order once your booth contract is signed.</Notice></div> : null}
            {o.status === "CANCELLED" && o.cancel_reason ? <div className="mb-2"><Notice tone="amber">Cancelled: {o.cancel_reason}</Notice></div> : null}
            <LinesTable order={o} />
            <p className="mt-2 text-right text-[14px] font-semibold tabular-nums">
              Total {money(o.total, o.currency)}{o.unpriced_lines ? <span className="font-normal text-label"> + extra items priced by the organizer</span> : null}
            </p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// --- review ------------------------------------------------------------------------------

export function OrderReviewPage({ record, code, onSignedOut }: { record: ExhibitorRecord; code: string; onSignedOut: () => void }) {
  const id = record.exhibitor_lead_id;
  const fetcher = useCallback(async () => {
    const detail = await call(api.GET("/api/v1/portal/exhibitors/{lead_id}/order-forms/{code}", { params: { path: { lead_id: id, code } } }));
    const open = detail.open_order;
    const quote = open ? await call(api.POST("/api/v1/portal/exhibitors/{lead_id}/orders/{order_id}/quote", { params: { path: { lead_id: id, order_id: open.id } } })) : null;
    return { detail, quote };
  }, [id, code]);
  const [state, reload] = useLoad(fetcher, onSignedOut);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formPath = `/e/${id}/forms/${code}`;
  if (state.kind === "loading") return <Loading />;
  if (state.kind === "error") return <div className="flex flex-col gap-6"><Back to={formPath}>Back to the form</Back><Failed message={state.message} onRetry={() => void reload()} /></div>;
  const { detail: d, quote } = state.data;
  const send = async () => {
    if (!quote) return;
    setBusy(true);
    setError(null);
    try {
      const sent = await call(api.POST("/api/v1/portal/exhibitors/{lead_id}/orders/{order_id}/submit", { params: { path: { lead_id: id, order_id: quote.id } }, body: { version: quote.version } }));
      pendingFlash = `Order ${sent.order_number ?? ""} sent. The organizer reviews it and confirms the total.`;
      navigate(formPath);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return onSignedOut();
      setError(e instanceof ApiError && Object.keys(e.fields).length ? `${e.message} ${Object.values(e.fields).join(" ")}` : messageOf(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Back to={formPath}>Back to the form</Back>
        <h1 className="text-[24px] leading-8 font-semibold tracking-[-0.01em]">Review Order · {d.code} {d.title}</h1>
        <p className="text-[14px] text-muted">{d.company_name} · Booth {d.booth_code ?? ""}</p>
      </div>
      {error ? <Notice>{error}</Notice> : null}
      {!quote ? (
        <Panel><p className="text-[14px] text-muted">There is nothing to send on this form. <a href={href(formPath)} onClick={(e) => { e.preventDefault(); navigate(formPath); }} className="text-link hover:underline">Go back to the form</a> to add items.</p></Panel>
      ) : (
        <>
          {periodNotice(quote.price_period)}
          <Panel title="Order Summary" aside={quote.price_period ? <span className="text-[13px] text-label">{label(quote.price_period)}s</span> : null}>
            {quote.lines.length ? <LinesTable order={quote} /> : <p className="text-[14px] text-muted">No items.</p>}
            <p className="mt-3 text-right text-[16px] font-semibold tabular-nums">Total {money(quote.total, quote.currency)}</p>
            {quote.unpriced_lines ? <p className="mt-1 text-right text-[13px] text-label">Extra items are priced by the organizer and added to the total.</p> : null}
            {quote.files.length ? <p className="mt-4 text-[14px]">Attachments: {quote.files.map((f) => f.file_name).join(", ")}</p> : null}
            {quote.remarks ? <p className="mt-2 text-[14px] whitespace-pre-line">Remarks: {quote.remarks}</p> : null}
          </Panel>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px] text-muted">Prices are fixed when you send. The organizer reviews the order and sends payment details.</p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => navigate(formPath)}>Change Order</Button>
              <Button variant="primary" loading={busy} disabled={quote.price_period === null} onClick={() => void send()}><Send aria-hidden />Send Order</Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
