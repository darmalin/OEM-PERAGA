import { useQuery } from "@tanstack/react-query";

import type { ExhibitorLead } from "@/features/exhibitors/queries";
import { formatDateTime, formatMoney } from "@/lib/format";
import { Indicator } from "@/ui/indicator";
import { PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, TableSkeleton } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

import { OrderFlags } from "./order-flags";
import { leadOrdersQuery, PROGRESS, type StaffOrderRow } from "./queries";

/** Order forms of one exhibitor: progress on each published form, then the orders sent. */
export function LeadOrdersTab({ lead, timezone }: { lead: ExhibitorLead; timezone?: string | undefined }) {
  const q = useQuery({ ...leadOrdersQuery(lead.id), enabled: lead.stage === "EXHIBITOR" });
  if (lead.stage !== "EXHIBITOR") {
    return <EmptyState title="Order forms open in the portal once the lead is converted to an exhibitor." />;
  }
  if (q.isPending) return <TableSkeleton rows={4} label="Loading orders" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const { forms, orders } = q.data;
  const done = forms.filter((f) => f.progress === "SUBMITTED" || f.progress === "APPROVED" || f.progress === "NOT_REQUIRED").length;
  const columns: Column<StaffOrderRow>[] = [
    { key: "number", header: "Order", cell: (o) => <span className="tabular">{o.order_number}</span> },
    { key: "form", header: "Form", cell: (o) => `${o.form_code} · ${o.form_title}` },
    { key: "status", header: "Status", cell: (o) => <OrderFlags order={o} /> },
    { key: "total", header: "Total", className: "text-right", cell: (o) => <span className="tabular">{formatMoney(o.total, o.currency)}</span> },
    { key: "sent", header: "Sent", hideBelow: "lg", cell: (o) => <span className="tabular">{formatDateTime(o.submitted_at, timezone)}</span> },
  ];
  return (
    <div className="flex flex-col gap-6 py-2">
      <section>
        <PanelHeader title={forms.length ? `Forms: ${done} of ${forms.length} done` : "Forms"} />
        {forms.length === 0 ? (
          <p className="px-5 py-4 text-[13px] text-label">No order forms are published in this edition.</p>
        ) : (
          <ul className="grid grid-cols-1 gap-x-6 gap-y-2 px-5 py-4 sm:grid-cols-2">
            {forms.map((f) => (
              <li key={f.form_id} className="flex items-center justify-between gap-3 text-[14px]">
                <span className="min-w-0 truncate"><span className="tabular text-label">{f.code}</span> {f.title}</span>
                <Indicator value={f.progress} text={PROGRESS[f.progress]} />
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <PanelHeader title="Orders Sent" />
        {orders.length === 0 ? (
          <p className="px-5 py-4 text-[13px] text-label">Nothing sent yet.</p>
        ) : (
          <ListTable
            caption={`Orders of ${lead.company_name}`}
            rows={orders}
            columns={columns}
            rowKey={(o) => o.id}
            rowLink={(o) => ({ to: "/app/exhibitor-orders/$orderId", params: { orderId: o.id } })}
          />
        )}
      </section>
    </div>
  );
}
