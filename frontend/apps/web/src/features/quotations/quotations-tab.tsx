import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Plus } from "lucide-react";

import type { ExhibitorLead } from "@/features/exhibitors/queries";
import { can, useMe } from "@/lib/auth";
import { formatDate, formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, TableSkeleton } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";

import { leadQuotationsQuery, type Quotation, quotationSettingsQuery } from "./queries";

const num = (v: string) => String(Number(v));

/** Every quotation of the lead, newest first: the history. */
export function QuotationsTab({ lead }: { lead: ExhibitorLead }) {
  const me = useMe();
  const q = useQuery(leadQuotationsQuery(lead.id));
  const settings = useQuery(quotationSettingsQuery(lead.edition_id));
  const canWrite = can(me, "exhibitor_lead.update") && lead.stage !== "LOST";
  const ready = settings.data?.exists ?? false;

  const columns: Column<Quotation>[] = [
    { key: "number", header: "Number", cell: (r) => <span className="tabular font-medium">{r.number}</span> },
    { key: "date", header: "Date", cell: (r) => <span className="tabular">{formatDate(r.issued_on)}</span>, hideBelow: "lg" },
    { key: "stand", header: "Stand", cell: (r) => `${label("stand_type", r.stand_type)} · ${num(r.charged_sqm)} sqm${r.booth_code ? ` · ${r.booth_code}` : ""}` },
    { key: "total", header: "Total", cell: (r) => <span className="tabular">{formatMoney(r.total_amount, r.currency)}</span>, className: "text-right" },
    { key: "status", header: "Status", cell: (r) => <Indicator value={r.status} group="quotation_status" /> },
    { key: "by", header: "Made By", cell: (r) => r.created_by_name ?? "", hideBelow: "xl" },
  ];

  return (
    <section>
      <PanelHeader
        title="Quotations"
        actions={
          canWrite && ready ? (
            <Button asChild size="sm" variant="primary">
              <Link to="/app/exhibitor-leads/$leadId/quotations/new" params={{ leadId: lead.id }}><Plus aria-hidden />New Quotation</Link>
            </Button>
          ) : null
        }
      />
      {settings.data && !ready ? (
        <p className="mx-5 mt-4 rounded-[8px] bg-[var(--amber-bg)] px-4 py-3 text-[13px] text-[var(--amber-fg)]">
          Quotations need the edition's quotation settings (number code, rates, terms, signer).{" "}
          {can(me, "booth.manage") ? <Link to="/app/quotation-settings" className="font-medium underline">Open Quotation Settings</Link> : "Ask an exhibition admin to set them up."}
        </p>
      ) : null}
      {q.isPending ? (
        <TableSkeleton rows={3} label="Loading quotations" />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : q.data.length === 0 ? (
        <EmptyState title="No quotation yet. Make one from the booth or space the company wants." />
      ) : (
        <ListTable
          caption={`Quotations of ${lead.company_name}`}
          rows={q.data}
          columns={columns}
          rowKey={(r) => r.id}
          rowLink={(r) => ({ to: "/app/exhibitor-leads/$leadId/quotations/$quotationId", params: { leadId: lead.id, quotationId: r.id } })}
        />
      )}
    </section>
  );
}
