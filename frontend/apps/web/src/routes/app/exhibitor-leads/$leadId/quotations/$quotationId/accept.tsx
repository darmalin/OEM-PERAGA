import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { quotationQuery } from "@/features/quotations/queries";
import { formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/quotations/$quotationId/accept")({ component: AcceptQuotation });

/** What accepting does, said before it happens (docs/EXHIBITOR_QUOTATIONS.md decision Q9). */
function AcceptQuotation() {
  const { leadId, quotationId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const q = useQuery(quotationQuery(quotationId));
  const [busy, setBusy] = useState(false);
  const back = { to: "/app/exhibitor-leads/$leadId/quotations/$quotationId", label: q.data ? `Quotation ${q.data.number}` : "Quotation", params: { leadId, quotationId } };

  const submit = async () => {
    if (!q.data) return;
    setBusy(true);
    try {
      const out = await call(api.POST("/api/v1/quotations/{quotation_id}/accept", { params: { path: { quotation_id: quotationId } }, body: { version: q.data.version } }));
      queryClient.setQueryData(quotationQuery(quotationId).queryKey, out);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", leadId] });
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      void queryClient.invalidateQueries({ queryKey: ["booths"] });
      notifySuccess(`Quotation ${out.number} accepted`, formatMoney(out.total_amount, out.currency));
      await navigate({ to: "/app/exhibitor-leads/$leadId/quotations/$quotationId", params: { leadId, quotationId } });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const l = lead.data;
  const d = q.data;
  const canHold = l?.stage === "OPPORTUNITY" || l?.stage === "EXHIBITOR";
  return (
    <Page className="max-w-[760px]">
      <PageHead title="Accept Quotation" back={back} meta="The company agreed to this quotation." />
      <Panel>
        {q.isPending || lead.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} /> : lead.isError ? <ErrorState error={lead.error} /> : d && l ? (
          <>
            <Section title={`${d.number} · ${formatMoney(d.total_amount, d.currency)}`}>
              <ul className="flex list-disc flex-col gap-2 pl-5 text-[13px]">
                {d.booth_id && d.booth_id !== l.booth_id ? (
                  <li>{canHold ? `The lead holds booth ${d.booth_code} at ${formatMoney(d.gross_amount, d.currency)}.` : `Booth ${d.booth_code} is held at the quoted price once the lead is an Opportunity and chooses it.`}</li>
                ) : l.booth_id ? (
                  <li>The agreed price of booth {l.booth_code} becomes {formatMoney(d.gross_amount, d.currency)}.</li>
                ) : (
                  <li>When the lead holds a booth, it takes the quoted price {formatMoney(d.gross_amount, d.currency)}.</li>
                )}
                <li>
                  {l.stage === "EXHIBITOR" ? "The Draft contract" : "The contract made at Convert"} takes the price, the discount
                  {Number(d.vat_rate) > 0 ? ", the VAT" : ""} and the terms of payment: total {formatMoney(d.total_amount, d.currency)}.
                </li>
                <li>Another accepted quotation of this lead, if any, becomes Superseded.</li>
              </ul>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId/quotations/$quotationId" params={{ leadId, quotationId }}>Back</Link></Button>
              <Button variant="primary" loading={busy} onClick={() => void submit()}>Accept Quotation</Button>
            </FormActions>
          </>
        ) : null}
      </Panel>
    </Page>
  );
}
