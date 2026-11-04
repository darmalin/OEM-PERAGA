import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Paperclip } from "lucide-react";

import { can, useMe } from "@/lib/auth";
import { formatDate, formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Metric } from "@/ui/metric";
import { EmptyState, ErrorState, TableSkeleton } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

import { contractQuery, type ExhibitorLead, type Payment, paymentsQuery } from "./queries";

/** Installments recorded against the signed contract and what is still owed. */
export function PaymentsTab({ lead }: { lead: ExhibitorLead; timezone?: string }) {
  const me = useMe();
  const exhibitor = lead.stage === "EXHIBITOR";
  const contract = useQuery({ ...contractQuery(lead.id), enabled: exhibitor });
  const q = useQuery({ ...paymentsQuery(lead.id), enabled: exhibitor });
  if (!exhibitor) return <EmptyState title="Payments are recorded after the lead is converted and the contract is signed." />;
  if (q.isPending || contract.isPending) return <TableSkeleton rows={4} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (contract.isError) return <ErrorState error={contract.error} onRetry={() => void contract.refetch()} />;
  const p = q.data;
  const signed = contract.data.status === "SIGNED";
  const record = signed && can(me, "exhibitor_payment.record") && Number(p.outstanding_amount) > 0 ? (
    <Button asChild variant="primary">
      <Link to="/app/exhibitor-leads/$leadId/payments/new" params={{ leadId: lead.id }}>Record Payment</Link>
    </Button>
  ) : null;
  const money = (v: string) => formatMoney(v, p.currency);
  const columns: Column<Payment>[] = [
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
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line px-5 py-5 max-md:px-4">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 md:grid-cols-4">
          <Metric label="Contract Total" value={money(p.total_amount)} />
          <Metric label="Verified" value={money(p.verified_amount)} />
          <Metric label="Pending" value={money(p.pending_amount)} />
          <Metric label="Outstanding" value={money(p.outstanding_amount)} hint={<Indicator value={p.payment_state} group="payment_state" />} />
        </div>
        {record}
      </div>
      {!signed ? (
        <EmptyState title="Payments can be recorded once the contract is signed." />
      ) : p.items.length === 0 ? (
        <EmptyState title="No payments recorded yet." action={record ?? undefined} />
      ) : (
        <ListTable
          caption="Payments"
          rows={p.items}
          columns={columns}
          rowKey={(x) => x.id}
          rowLink={(x) => ({ to: "/app/exhibitor-leads/$leadId/payments/$paymentId", params: { leadId: lead.id, paymentId: x.id } })}
        />
      )}
    </div>
  );
}
