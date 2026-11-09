import { api, call, downloadFile } from "@ems/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { Download } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { OrderFlags } from "@/features/order-forms/order-flags";
import { ORDER_STATUSES, orderFormsQuery, type StaffOrderRow } from "@/features/order-forms/queries";
import { useEdition } from "@/lib/edition";
import { formatDateTime, formatMoney } from "@/lib/format";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FilterBar, SearchFilter, SelectFilter } from "@/ui/filters";
import { ListBody } from "@/ui/list";
import { Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

const STATUS = ["SUBMITTED", "RETURNED", "APPROVED", "CANCELLED", "ALL"] as const;
const search = z.object({
  // Staff open the queue to review, so it starts on what waits for them.
  status: z.enum(STATUS).default("SUBMITTED"),
  form: z.string().optional(),
  q: z.string().optional(),
  page: z.number().int().min(1).default(1),
  page_size: z.number().int().default(50),
});
type Search = z.infer<typeof search>;

export const Route = createFileRoute("/app/exhibitor-orders/")({ validateSearch: search, component: ExhibitorOrders });

function ExhibitorOrders() {
  const { edition } = useEdition();
  const s = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const set = (patch: Partial<Search>) => void navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }), replace: true });
  const forms = useQuery({ ...orderFormsQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const query = useQuery({
    queryKey: ["exhibitor-orders", edition?.id, "list", s],
    enabled: Boolean(edition),
    placeholderData: keepPreviousData,
    queryFn: () =>
      call(
        api.GET("/api/v1/exhibitor-orders", {
          params: {
            query: {
              edition_id: edition!.id,
              status: s.status === "ALL" ? undefined : s.status,
              form_id: s.form,
              q: s.q,
              page: s.page,
              page_size: s.page_size,
            },
          },
        }),
      ),
  });
  const [exporting, setExporting] = useState(false);
  if (!edition) return <Page><NoEdition /></Page>;
  const filtered = Boolean(s.q || s.form || s.status !== "SUBMITTED");
  const clear = () => void navigate({ search: { status: "SUBMITTED", page: 1, page_size: s.page_size }, replace: true });
  const form = forms.data?.items.find((f) => f.id === s.form);
  const exportForm = async () => {
    if (!form) return;
    setExporting(true);
    try {
      const params = new URLSearchParams({ edition_id: edition.id, form_id: form.id });
      if (s.status !== "ALL") params.set("status", s.status);
      await downloadFile(`/api/v1/exhibitor-orders/export?${params.toString()}`);
    } catch (e) {
      notifyError(e);
    } finally {
      setExporting(false);
    }
  };
  const columns: Column<StaffOrderRow>[] = [
    { key: "number", header: "Order", cell: (o) => <span className="tabular">{o.order_number}</span> },
    { key: "company", header: "Exhibitor", cell: (o) => <span className="font-medium">{o.company_name}</span> },
    { key: "booth", header: "Booth", hideBelow: "lg", cell: (o) => <span className="tabular">{o.booth_code ?? ""}</span> },
    { key: "form", header: "Form", hideBelow: "md", cell: (o) => `${o.form_code} · ${o.form_title}` },
    { key: "status", header: "Status", cell: (o) => <OrderFlags order={o} /> },
    { key: "total", header: "Total", className: "text-right", cell: (o) => <span className="tabular">{formatMoney(o.total, o.currency)}</span> },
    { key: "sent", header: "Sent", hideBelow: "xl", cell: (o) => <span className="tabular">{formatDateTime(o.submitted_at, edition.timezone)}</span> },
  ];
  return (
    <Page>
      <PageHead
        edition
        title="Orders"
        meta={query.data ? `${query.data.total.toLocaleString("en")} ${s.status === "ALL" ? "sent" : (ORDER_STATUSES[s.status] ?? "").toLowerCase()} in ${edition.code}` : edition.code}
        actions={form ? <Button loading={exporting} onClick={() => void exportForm()}><Download aria-hidden />Export Form {form.code}</Button> : null}
      />
      <Panel>
        <FilterBar active={filtered} onClear={clear}>
          <SearchFilter value={s.q} onChange={(q) => set({ q })} placeholder="Search exhibitor or order number" />
          <SelectFilter
            label="Status"
            value={s.status === "ALL" ? undefined : s.status}
            onChange={(v) => set({ status: (v as Search["status"] | undefined) ?? "ALL" })}
            allLabel="All sent"
            options={Object.entries(ORDER_STATUSES).map(([value, label]) => ({ value, label }))}
          />
          <SelectFilter
            label="Form"
            value={s.form}
            onChange={(form) => set({ form })}
            allLabel="All forms"
            options={(forms.data?.items ?? []).map((f) => ({ value: f.id, label: `${f.code} · ${f.title}` }))}
          />
        </FilterBar>
        <ListBody
          query={query}
          onPage={(page) => set({ page })}
          onPageSize={(page_size) => set({ page_size })}
          empty={
            filtered ? (
              <EmptyState title="No orders match these filters." action={<Button onClick={clear}>Clear Filters</Button>} />
            ) : (
              <EmptyState
                title="No orders wait for review. Orders appear here when exhibitors send them from the portal."
                action={<Button asChild><Link to="/app/exhibitor-orders" search={{ status: "ALL", page: 1, page_size: s.page_size }}>Show All Sent</Link></Button>}
              />
            )
          }
        >
          {(rows) => (
            <ListTable
              caption="Exhibitor orders"
              rows={rows}
              columns={columns}
              rowKey={(o) => o.id}
              rowLink={(o) => ({ to: "/app/exhibitor-orders/$orderId", params: { orderId: o.id } })}
            />
          )}
        </ListBody>
      </Panel>
    </Page>
  );
}
