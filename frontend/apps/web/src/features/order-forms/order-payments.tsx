import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Paperclip } from "lucide-react";

import { can, useMe } from "@/lib/auth";
import { formatDate, formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Metric } from "@/ui/metric";
import { PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, TableSkeleton } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

import { type OrderPayment, orderPaymentsQuery, type StaffOrder } from "./queries";

/** Installments recorded against an approved order (Phase 7), like the contract's Payments tab. */
export function OrderPayments({ order: o }: { order: StaffOrder }) {
  const me = useMe();
  const q = useQuery(orderPaymentsQuery(o.id));
  if (q.isPending) return <TableSkeleton rows={3} label="Loading payments" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const p = q.data;
  const money = (v: string) => formatMoney(v, p.currency);
  const record = can(me, "exhibitor_payment.record") && Number(p.outstanding_amount) > 0 ? (
    <Button asChild size="sm" variant="primary">
      <Link to="/app/exhibitor-orders/$orderId/payments/new" params={{ orderId: o.id }}>Record Payment</Link>
    </Button>
  ) : null;
  const columns: Column<OrderPayment>[] = [
    { key: "paid_on", header: "Paid On", cell: (x) => <span className="tabular">{formatDate(x.paid_on)}</span> },
    { key: "amount", header: "Amount", cell: (x) => <span className="tabular">{money(x.amount)}</span> },
    { key: "status", header: "Status", cell: (x) => <Indicator value={x.status} group="payment_status" /> },
    { key: "method", header: "Method", hideBelow: "lg", cell: (x) => label("payment_method", x.method) },
    { key: "reference", header: "Reference", hideBelow: "xl", cell: (x) => <span className="text-muted">{x.reference ?? ""}</span> },
    {
      key: "proof",
      header: "Proof",
      hideBelow: "lg",
      cell: (x) => (x.has_proof ? <span className="inline-flex items-center gap-1 text-muted"><Paperclip className="size-3.5" aria-hidden />Attached</span> : <span className="text-label">None</span>),
    },
  ];
  return (
    <div>
      <PanelHeader title="Payments" actions={record} />
      <div className="grid grid-cols-2 gap-x-8 gap-y-4 border-b border-line px-5 py-5 md:grid-cols-4">
        <Metric label="Order Total" value={money(p.total_amount)} />
        <Metric label="Verified" value={money(p.verified_amount)} />
        <Metric label="Pending" value={money(p.pending_amount)} />
        <Metric label="Outstanding" value={money(p.outstanding_amount)} hint={<Indicator value={p.payment_state} group="payment_state" />} />
      </div>
      {p.items.length === 0 ? (
        <EmptyState title="No payments recorded yet." action={record ?? undefined} />
      ) : (
        <ListTable
          caption={`Payments of order ${o.order_number ?? ""}`}
          rows={p.items}
          columns={columns}
          rowKey={(x) => x.id}
          rowLink={(x) => ({ to: "/app/exhibitor-orders/$orderId/payments/$paymentId", params: { orderId: o.id, paymentId: x.id } })}
        />
      )}
    </div>
  );
}
