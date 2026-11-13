import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { quotationQuery } from "@/features/quotations/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/quotations/$quotationId/cancel")({ component: CancelQuotation });

function CancelQuotation() {
  const { leadId, quotationId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery(quotationQuery(quotationId));
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const back = { to: "/app/exhibitor-leads/$leadId/quotations/$quotationId", label: q.data ? `Quotation ${q.data.number}` : "Quotation", params: { leadId, quotationId } };

  const submit = async () => {
    if (!q.data) return;
    if (!reason.trim()) {
      setError("Say why, e.g. the company chose another booth.");
      return;
    }
    setBusy(true);
    try {
      const out = await call(api.POST("/api/v1/quotations/{quotation_id}/cancel", { params: { path: { quotation_id: quotationId } }, body: { reason: reason.trim(), version: q.data.version } }));
      queryClient.setQueryData(quotationQuery(quotationId).queryKey, out);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", leadId, "quotations"] });
      notifySuccess(`Quotation ${out.number} cancelled`);
      await navigate({ to: "/app/exhibitor-leads/$leadId/quotations/$quotationId", params: { leadId, quotationId } });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="max-w-[720px]">
      <PageHead title="Cancel Quotation" back={back} meta="It stays in the history with the reason." />
      <Panel>
        {q.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} /> : (
          <>
            <Section title={q.data.number}>
              <Field label="Reason" required error={error}>
                {(p) => <Textarea {...p} rows={3} maxLength={1000} value={reason} onChange={(e) => { setReason(e.target.value); setError(undefined); }} />}
              </Field>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId/quotations/$quotationId" params={{ leadId, quotationId }}>Back</Link></Button>
              <Button variant="danger" loading={busy} onClick={() => void submit()}>Cancel Quotation</Button>
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}
