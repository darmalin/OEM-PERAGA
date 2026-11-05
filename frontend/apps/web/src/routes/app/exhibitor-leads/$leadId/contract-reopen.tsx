import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { contractQuery, exhibitorLeadQuery, paymentsQuery } from "@/features/exhibitors/queries";
import { handleFormError } from "@/lib/forms";
import { formatMoney } from "@/lib/format";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/contract-reopen")({ component: ReopenContract });

/** A signed contract back to Draft, e.g. after the wrong PDF was uploaded (known-gaps F8). */
function ReopenContract() {
  const { leadId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const contract = useQuery(contractQuery(leadId));
  const payments = useQuery(paymentsQuery(leadId));
  const form = useForm<{ reason: string }>({ defaultValues: { reason: "" } });
  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };

  const onSubmit = form.handleSubmit(async (v) => {
    if (!contract.data) return;
    try {
      const updated = await call(
        api.POST("/api/v1/exhibitor-leads/{lead_id}/contract/reopen", {
          params: { path: { lead_id: leadId } },
          body: { reason: v.reason.trim(), version: contract.data.version },
        }),
      );
      queryClient.setQueryData(contractQuery(leadId).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", leadId] });
      notifySuccess("Contract reopened", "The exhibitor can fill it in and upload the signed PDF again.");
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId }, search: { tab: "contract" } });
    } catch (e) {
      handleFormError(e, form.setError, ["reason"]);
    }
  });

  const p = payments.data;
  // Same rule as the API: payments taken against the signed total must be rejected first.
  const blocking = p ? Number(p.pending_amount) + Number(p.verified_amount) > 0 : false;
  const toLead = <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }} search={{ tab: "contract" }}>Cancel</Link></Button>;
  return (
    <Page className="max-w-[800px]">
      <PageHead title="Reopen Contract" back={back} />
      <Panel>
        {contract.isPending || payments.isPending ? <FormSkeleton /> : contract.isError ? <ErrorState error={contract.error} /> : payments.isError ? <ErrorState error={payments.error} /> : contract.data.status !== "SIGNED" ? (
          <EmptyState title="Only a signed contract can be reopened." action={toLead} />
        ) : blocking && p ? (
          <EmptyState
            title={
              Number(p.verified_amount) > 0
                ? `This contract has ${formatMoney(p.verified_amount, p.currency)} in verified payments, so it cannot be reopened.`
                : `This contract has ${formatMoney(p.pending_amount, p.currency)} in pending payments. Reject them before reopening: they were recorded against the signed total.`
            }
            action={<Button asChild><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }} search={{ tab: "payments" }}>Open Payments</Link></Button>}
          />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title={`Contract ${contract.data.contract_number ?? ""}`}>
              <ul className="mb-4 max-w-2xl list-disc space-y-1 pl-5 text-[13px] text-muted">
                <li>The contract goes back to Draft. The exhibitor can change the details and upload a signed PDF again.</li>
                <li>The current signed PDF is kept and its record stays in the audit log; it is no longer the contract's file.</li>
                <li>The booth can change again while the contract is a Draft, and the price follows it.</li>
              </ul>
              <Field label="Reason" required className="max-w-xl" help="Kept in the audit log." error={form.formState.errors.reason?.message}>
                {(f) => <Textarea {...f} {...form.register("reason", { validate: (v) => v.trim() !== "" || "Say why the contract is reopened." })} />}
              </Field>
            </Section>
            <FormActions>
              {toLead}
              <Button type="submit" variant="danger" loading={form.formState.isSubmitting}>Reopen Contract</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
