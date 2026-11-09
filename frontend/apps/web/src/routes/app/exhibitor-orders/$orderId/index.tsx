import { api, ApiError, call, downloadFile } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Check, Download, RotateCcw, XCircle } from "lucide-react";
import { useState } from "react";

import { AnswersView } from "@/features/order-forms/answers";
import { OrderFlags } from "@/features/order-forms/order-flags";
import { OrderPayments } from "@/features/order-forms/order-payments";
import { DETAILS_TYPES, exhibitorOrderQuery, PERIODS, type StaffOrder } from "@/features/order-forms/queries";
import { can, useMe } from "@/lib/auth";
import { formatBytes, formatDateTime, formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Input } from "@/ui/input";
import { Facts, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-orders/$orderId/")({ component: OrderDetail });

const BACK = { to: "/app/exhibitor-orders", label: "Orders" };
const PURPOSES: Record<string, string> = {
  LOGO: "Logo",
  PRODUCT_IMAGE: "Product image",
  FITTING_LOCATION: "Fitting location",
  VISA_LIST: "Visa list",
  OTHER: "Other file",
};

function OrderDetail() {
  const { orderId } = Route.useParams();
  const me = useMe();
  const queryClient = useQueryClient();
  const q = useQuery(exhibitorOrderQuery(orderId));
  const [busy, setBusy] = useState(false);
  if (q.isPending) return <Page><PageHead title="Loading order" back={BACK} /><Panel><FormSkeleton /></Panel></Page>;
  if (q.isError) return <Page><PageHead title="Order" back={BACK} /><Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel></Page>;
  const o = q.data;
  const review = can(me, "exhibitor_order.review");
  const waiting = o.status === "SUBMITTED";
  const blockers = [
    o.unpriced_lines ? `Set a price on ${o.unpriced_lines === 1 ? "the extra item" : `the ${o.unpriced_lines} extra items`} first.` : null,
    o.waiting_for_contract ? "The booth contract is not signed yet; orders that cost money wait for it." : null,
  ].filter((x): x is string => Boolean(x));
  const saved = (updated: StaffOrder, message: string) => {
    queryClient.setQueryData(exhibitorOrderQuery(orderId).queryKey, updated);
    void queryClient.invalidateQueries({ queryKey: ["exhibitor-orders", updated.id] });
    void queryClient.invalidateQueries({ queryKey: ["exhibitor-orders"], exact: false });
    void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", updated.exhibitor_lead_id, "orders"] });
    notifySuccess(message);
  };
  const approve = async () => {
    setBusy(true);
    try {
      const updated = await call(
        api.POST("/api/v1/exhibitor-orders/{order_id}/review", { params: { path: { order_id: orderId } }, body: { decision: "APPROVED", version: o.version } }),
      );
      saved(updated, `Order ${updated.order_number ?? ""} approved`);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  const actions = review && o.status !== "CANCELLED" ? (
    <>
      {waiting ? (
        <>
          <Button asChild variant="ghost"><Link to="/app/exhibitor-orders/$orderId/return" params={{ orderId }}><RotateCcw aria-hidden />Return to Exhibitor</Link></Button>
          <Button variant="primary" disabled={blockers.length > 0} loading={busy} onClick={() => void approve()}><Check aria-hidden />Approve</Button>
        </>
      ) : null}
      <Button asChild variant="ghost"><Link to="/app/exhibitor-orders/$orderId/cancel" params={{ orderId }}><XCircle aria-hidden />Cancel Order</Link></Button>
    </>
  ) : null;
  return (
    <Page>
      <PageHead
        back={BACK}
        title={`Order ${o.order_number ?? ""}`}
        meta={`${o.form_code} · ${o.form_title} · sent ${formatDateTime(o.submitted_at)}`}
        indicators={<OrderFlags order={o} />}
        actions={actions}
      />
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-6">
          {waiting && review && blockers.length ? (
            <p role="status" className="rounded-[8px] px-4 py-3 text-[13px]" style={{ color: "var(--amber-fg)", background: "var(--amber-bg)" }}>{blockers.join(" ")}</p>
          ) : null}
          {o.booth_changed && (o.status === "SUBMITTED" || o.status === "RETURNED") ? (
            <p role="status" className="rounded-[8px] px-4 py-3 text-[13px]" style={{ color: "var(--amber-fg)", background: "var(--amber-bg)" }}>
              Booth changed since submit: sent for {o.booth_code_at_submit} ({Number(o.area_sqm_at_submit)} m²), now {o.booth_code ?? "no booth"}. Return the order if the quantities depend on the booth size.
            </p>
          ) : null}
          {o.lines.length ? (
            <Panel>
              <PanelHeader title="Items" actions={<span className="text-[14px] font-semibold tabular">Total {formatMoney(o.total, o.currency)}</span>} />
              <Lines order={o} canPrice={review && waiting} onSaved={saved} />
            </Panel>
          ) : null}
          {o.status === "APPROVED" && Number(o.total) > 0 ? <Panel><OrderPayments order={o} /></Panel> : null}
          {o.details_type ? (
            <Panel>
              <PanelHeader title={`Answers · ${DETAILS_TYPES[o.details_type]}`} />
              <div className="p-5"><AnswersView type={o.details_type} answers={o.details as Record<string, unknown>} /></div>
            </Panel>
          ) : null}
          {o.files.length ? (
            <Panel>
              <PanelHeader title="Attachments" />
              <ul className="flex flex-col gap-2 p-5 text-[14px]">
                {o.files.map((f) => (
                  <li key={f.id} className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="ghost" onClick={() => void downloadFile(`/api/v1/exhibitor-orders/${o.id}/files/${f.id}`, f.file_name).catch(notifyError)}>
                      <Download aria-hidden />{f.file_name}
                    </Button>
                    <span className="text-[12px] text-label">{PURPOSES[f.purpose] ?? f.purpose} · {formatBytes(f.size_bytes)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </div>
        <aside className="flex flex-col gap-6">
          <Panel>
            <PanelHeader title="Exhibitor" />
            <div className="p-5">
              <Facts
                items={[
                  ["Company", <Link key="c" to="/app/exhibitor-leads/$leadId" params={{ leadId: o.exhibitor_lead_id }} search={{ tab: "orders" }} className="text-link hover:underline">{o.company_name}</Link>],
                  ["Booth", o.booth_code],
                  ["Contract", o.contract_signed ? "Signed" : "Not signed yet"],
                ]}
              />
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Order" />
            <div className="p-5">
              <Facts
                items={[
                  ["Price", o.price_period ? PERIODS[o.price_period] : null],
                  ["Sent For", o.booth_code_at_submit ? `${o.booth_code_at_submit}, ${Number(o.area_sqm_at_submit)} m²` : null],
                  ["Remarks", o.remarks],
                  ...(o.reviewed_at ? ([[o.status === "APPROVED" ? "Approved" : o.status === "CANCELLED" ? "Reviewed" : "Returned", `${formatDateTime(o.reviewed_at)} by ${o.reviewed_by_name ?? ""}`], ["Notes", o.review_notes]] as [string, string | null][]) : []),
                  ...(o.cancel_reason ? ([["Cancelled", o.cancel_reason]] as [string, string][]) : []),
                ]}
              />
            </div>
          </Panel>
        </aside>
      </div>
    </Page>
  );
}

function Lines({ order: o, canPrice, onSaved }: { order: StaffOrder; canPrice: boolean; onSaved: (o: StaffOrder, message: string) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px] text-[14px]">
        <caption className="sr-only">Items of order {o.order_number}</caption>
        <thead>
          <tr className="border-b border-line text-left text-[13px] text-label">
            <th scope="col" className="px-5 py-2.5 font-normal">Item</th>
            <th scope="col" className="px-3 py-2.5 text-right font-normal">Quantity</th>
            <th scope="col" className="px-3 py-2.5 text-right font-normal">Unit Price</th>
            <th scope="col" className="px-5 py-2.5 text-right font-normal">Amount</th>
          </tr>
        </thead>
        <tbody>
          {o.lines.map((l) => (
            <tr key={l.id} className="border-b border-line align-top last:border-0">
              <td className="px-5 py-3">
                <div className="flex items-start gap-3">
                  {l.has_image ? <img src={`/api/v1/exhibitor-orders/${o.id}/lines/${l.id}/image`} alt={l.name} className="size-14 shrink-0 rounded-[6px] border border-line object-contain" /> : null}
                  <div>
                    <div className="font-medium">{l.name}</div>
                    <div className="text-[12px] text-label">{[l.code, l.size, l.section, l.item_id ? null : "Extra item described by the exhibitor"].filter(Boolean).join(" · ")}</div>
                    {l.notes ? <div className="text-[12px] text-muted">{l.notes}</div> : null}
                  </div>
                </div>
              </td>
              <td className="px-3 py-3 text-right tabular">{l.quantity}{l.free_quantity ? <span className="block text-[12px] text-label">{l.free_quantity} free</span> : null}</td>
              <td className="px-3 py-3 text-right">
                {!l.item_id && canPrice ? <PriceInput order={o} lineId={l.id} current={l.unit_price ?? null} onSaved={onSaved} /> : l.unit_price == null ? <span className="text-label">Not priced</span> : <span className="tabular">{formatMoney(l.unit_price, o.currency)}</span>}
              </td>
              <td className="px-5 py-3 text-right tabular">{l.amount == null ? "" : formatMoney(l.amount, o.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PriceInput({ order: o, lineId, current, onSaved }: { order: StaffOrder; lineId: string; current: string | null; onSaved: (o: StaffOrder, message: string) => void }) {
  const [value, setValue] = useState(current ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const valid = /^\d+(\.\d{1,2})?$/.test(value);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const updated = await call(
        api.PATCH("/api/v1/exhibitor-orders/{order_id}/lines/{line_id}", {
          params: { path: { order_id: o.id, line_id: lineId } },
          body: { unit_price: value, version: o.version },
        }),
      );
      onSaved(updated, "Price saved");
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? e.message);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <Input aria-label="Unit price" aria-invalid={Boolean(error)} inputMode="decimal" className="w-32 text-right tabular" value={value} placeholder={o.currency} onChange={(e) => setValue(e.target.value.trim())} />
        <Button size="sm" disabled={!valid || value === (current ?? "")} loading={busy} onClick={() => void save()}>Set Price</Button>
      </div>
      {error ? <span className="text-[12px] text-required">{error}</span> : null}
    </div>
  );
}
