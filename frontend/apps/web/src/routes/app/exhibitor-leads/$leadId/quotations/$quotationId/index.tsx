import { downloadFile } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Ban, Check, Download, PencilLine } from "lucide-react";
import { useState } from "react";

import { exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { quotationQuery } from "@/features/quotations/queries";
import { QuotationSummary } from "@/features/quotations/summary";
import { can, useMe } from "@/lib/auth";
import { formatDate, formatDateTime } from "@/lib/format";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Facts, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/quotations/$quotationId/")({ component: QuotationPage });

function QuotationPage() {
  const { leadId, quotationId } = Route.useParams();
  const me = useMe();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const q = useQuery(quotationQuery(quotationId));
  const [busy, setBusy] = useState(false);
  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };

  if (q.isPending) return <Page><PageHead title="Quotation" back={back} /><Panel><FormSkeleton /></Panel></Page>;
  if (q.isError) return <Page><PageHead title="Quotation" back={back} /><Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel></Page>;
  const d = q.data;
  const open = d.status === "ISSUED" && can(me, "exhibitor_lead.update") && lead.data?.stage !== "LOST";

  const download = async () => {
    setBusy(true);
    try {
      await downloadFile(`/api/v1/quotations/${d.id}/pdf`, `Quotation ${d.number.replaceAll("/", "-")}.pdf`);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="max-w-[1000px]">
      <PageHead
        back={back}
        title={`Quotation ${d.number}`}
        meta={`${formatDate(d.issued_on)} · made by ${d.created_by_name ?? "unknown"} ${formatDateTime(d.created_at)}`}
        indicators={<Indicator value={d.status} group="quotation_status" />}
        actions={
          <div className="flex flex-wrap gap-2">
            {open ? (
              <>
                <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId/quotations/$quotationId/cancel" params={{ leadId, quotationId }}><Ban aria-hidden />Cancel Quotation</Link></Button>
                <Button asChild><Link to="/app/exhibitor-leads/$leadId/quotations/new" params={{ leadId }} search={{ replaces: d.id }}><PencilLine aria-hidden />Revise</Link></Button>
                <Button asChild><Link to="/app/exhibitor-leads/$leadId/quotations/$quotationId/accept" params={{ leadId, quotationId }}><Check aria-hidden />Accept</Link></Button>
              </>
            ) : null}
            <Button variant="primary" loading={busy} onClick={() => void download()}><Download aria-hidden />Download PDF</Button>
          </div>
        }
      />
      {d.status === "SUPERSEDED" && d.replaced_by_number ? (
        <p className="rounded-[8px] bg-[var(--gray-bg)] px-4 py-3 text-[13px] text-[var(--gray-fg)]">Replaced by quotation {d.replaced_by_number}.</p>
      ) : null}
      {d.status === "ACCEPTED" ? (
        <p className="rounded-[8px] bg-[var(--green-bg)] px-4 py-3 text-[13px] text-[var(--green-fg)]">Accepted {formatDateTime(d.accepted_at)}. The contract takes this price, discount, VAT, and terms.</p>
      ) : null}
      {d.status === "CANCELLED" ? (
        <p className="rounded-[8px] bg-[var(--gray-bg)] px-4 py-3 text-[13px] text-[var(--gray-fg)]">Cancelled {formatDateTime(d.cancelled_at)}: {d.cancel_reason}</p>
      ) : null}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <Panel>
          <PanelHeader title="Price" />
          <div className="p-5"><QuotationSummary q={d} /></div>
        </Panel>
        <Panel>
          <PanelHeader title="Letter" />
          <div className="p-5 text-[13px]">
            <Facts
              items={[
                ["To", d.recipient_company],
                ["Address", d.recipient_address ? <span key="a" className="whitespace-pre-line">{d.recipient_address}</span> : null],
                ["Attention", d.attention],
                ["Date", formatDate(d.issued_on)],
              ]}
            />
            <p className="mt-4 text-[12px] text-label">The PDF is printed from what was saved; later setting changes do not alter it.</p>
          </div>
        </Panel>
      </div>
    </Page>
  );
}
