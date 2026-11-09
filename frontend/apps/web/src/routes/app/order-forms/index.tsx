import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Copy } from "lucide-react";

import { formParts, orderFormsQuery, type OrderForm } from "@/features/order-forms/queries";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { formatDate } from "@/lib/format";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, NoEdition, TableSkeleton } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

export const Route = createFileRoute("/app/order-forms/")({ component: OrderForms });

const columns: Column<OrderForm>[] = [
  { key: "code", header: "No.", cell: (f) => <span className="tabular">{f.code}</span> },
  { key: "title", header: "Form", cell: (f) => <span className="font-medium">{f.title}</span> },
  {
    key: "status",
    header: "Status",
    cell: (f) => (f.is_published ? <Indicator value="ACTIVE" text="Published" /> : <Indicator value="DRAFT" text="Not Published" />),
  },
  { key: "parts", header: "Exhibitor Fills In", hideBelow: "lg", cell: (f) => <span className="text-muted">{formParts(f)}</span> },
  { key: "deadline", header: "Deadline", hideBelow: "md", cell: (f) => <span className="tabular">{formatDate(f.deadline_on)}</span> },
  { key: "closes", header: "Closes", hideBelow: "md", cell: (f) => <span className="tabular">{f.closes_on ? formatDate(f.closes_on) : <span className="text-label">Order Expired</span>}</span> },
];

function OrderForms() {
  const me = useMe();
  const { edition } = useEdition();
  const q = useQuery({ ...orderFormsQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  if (!edition) return <Page><NoEdition /></Page>;
  const manage = can(me, "order_form.manage");
  const actions = manage ? (
    <>
      <Button asChild><Link to="/app/order-forms/copy"><Copy aria-hidden />Copy from Edition</Link></Button>
      <Button asChild variant="primary"><Link to="/app/order-forms/new">Add Form</Link></Button>
    </>
  ) : null;
  const forms = q.data?.items ?? [];
  const published = forms.filter((f) => f.is_published).length;
  return (
    <Page>
      <PageHead
        edition
        title="Order Forms"
        meta={q.data ? `${forms.length} in ${edition.code}, ${published} published to the exhibitor portal` : edition.code}
        actions={actions}
      />
      <Panel>
        {q.isPending ? <TableSkeleton rows={6} label="Loading order forms" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : forms.length === 0 ? (
          <EmptyState
            title={`No order forms in ${edition.code} yet. Copy them from an earlier edition or add them one by one.`}
            action={actions ?? undefined}
          />
        ) : (
          <ListTable
            caption="Order forms"
            rows={forms}
            columns={columns}
            rowKey={(f) => f.id}
            rowLink={(f) => ({ to: "/app/order-forms/$formId", params: { formId: f.id } })}
          />
        )}
      </Panel>
    </Page>
  );
}
