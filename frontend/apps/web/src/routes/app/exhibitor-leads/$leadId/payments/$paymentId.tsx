import { ApiError, api, call, downloadFile, upload } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Download, FileUp } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { exhibitorLeadQuery, type Payment, paymentsQuery } from "@/features/exhibitors/queries";
import { can, useMe } from "@/lib/auth";
import { useEditionById } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input, Textarea } from "@/ui/input";
import { Facts, FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/payments/$paymentId")({ component: PaymentDetail });

function PaymentDetail() {
  const { leadId, paymentId } = Route.useParams();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const edition = useEditionById(lead.data?.edition_id);
  const q = useQuery(paymentsQuery(leadId));
  const payment = q.data?.items.find((p) => p.id === paymentId);
  const currency = q.data?.currency ?? "";
  return (
    <Page className="max-w-[1000px]">
      <PageHead
        title={payment ? formatMoney(payment.amount, currency) : "Payment"}
        indicators={payment ? <Indicator value={payment.status} group="payment_status" /> : null}
        back={{ to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } }}
      />
      <Panel>
        {q.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : !payment ? (
          <EmptyState title="Payment not found." />
        ) : (
          <>
            <Section title="Payment">
              <Facts
                items={[
                  ["Amount", formatMoney(payment.amount, currency)],
                  ["Paid On", formatDate(payment.paid_on)],
                  ["Method", label("payment_method", payment.method)],
                  ["Reference", payment.reference],
                  ["Notes", payment.notes],
                  ["Recorded", formatDateTime(payment.created_at, edition?.timezone)],
                  ...(payment.reviewed_at ? ([["Reviewed", formatDateTime(payment.reviewed_at, edition?.timezone)]] as [string, string][]) : []),
                ]}
              />
            </Section>
            <Proof leadId={leadId} payment={payment} />
            <Review leadId={leadId} payment={payment} />
          </>
        )}
      </Panel>
    </Page>
  );
}

function Proof({ leadId, payment }: { leadId: string; payment: Payment }) {
  const me = useMe();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const url = `/api/v1/exhibitor-leads/${leadId}/payments/${payment.id}/proof`;
  const editable = payment.status === "PENDING" && can(me, "exhibitor_payment.record");

  const send = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("version", String(payment.version));
    setBusy(true);
    try {
      await upload<Payment>(url, form);
      await queryClient.invalidateQueries({ queryKey: paymentsQuery(leadId).queryKey });
      setFile(null);
      notifySuccess("Proof attached");
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? null);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  const download = async () => {
    try {
      // The server names the file, with the extension of the uploaded proof.
      await downloadFile(url);
    } catch (e) {
      notifyError(e);
    }
  };

  if (!payment.has_proof && !editable) return null;
  return (
    <Section title="Proof">
      <div className="flex flex-wrap items-end gap-3">
        {payment.has_proof ? <Button onClick={() => void download()}><Download aria-hidden />Download Proof</Button> : null}
        {editable ? (
          <>
            <Field label={payment.has_proof ? "Replace Proof" : "Transfer Slip or Receipt"} help="PDF, JPG or PNG, up to 10 MB." error={error ?? undefined}>
              {(p) => <Input {...p} type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" className="py-1" onChange={(e) => { setError(null); setFile(e.target.files?.[0] ?? null); }} />}
            </Field>
            <Button disabled={!file} loading={busy} onClick={() => void send()}><FileUp aria-hidden />Attach</Button>
          </>
        ) : null}
      </div>
    </Section>
  );
}

function Review({ leadId, payment }: { leadId: string; payment: Payment }) {
  const me = useMe();
  const queryClient = useQueryClient();
  const form = useForm<{ notes: string }>({ defaultValues: { notes: "" } });
  if (payment.status !== "PENDING" || !can(me, "exhibitor_payment.verify")) return null;

  const decide = (decision: "VERIFIED" | "REJECTED") =>
    form.handleSubmit(async (v) => {
      if (decision === "REJECTED" && !v.notes.trim()) {
        form.setError("notes", { message: "Say why the payment is rejected." });
        return;
      }
      try {
        await call(
          api.POST("/api/v1/exhibitor-leads/{lead_id}/payments/{payment_id}/review", {
            params: { path: { lead_id: leadId, payment_id: payment.id } },
            body: { decision, notes: v.notes.trim() || null, version: payment.version },
          }),
        );
        await queryClient.invalidateQueries({ queryKey: paymentsQuery(leadId).queryKey });
        notifySuccess(decision === "VERIFIED" ? "Payment verified" : "Payment rejected");
      } catch (e) {
        handleFormError(e, form.setError, ["notes"]);
      }
    })();

  return (
    <form onSubmit={(e) => e.preventDefault()} noValidate>
      <Section title="Review">
        <p className="mb-3 max-w-2xl text-[13px] text-muted">Check the amount against the bank statement or the cash received. Verified payments count toward the contract total.</p>
        <Field label="Notes" help="Required when rejecting; replaces the notes above." className="max-w-xl" error={form.formState.errors.notes?.message}>
          {(p) => <Textarea {...p} {...form.register("notes")} />}
        </Field>
      </Section>
      <FormActions>
        <Button type="button" variant="danger" loading={form.formState.isSubmitting} onClick={() => void decide("REJECTED")}>Reject</Button>
        <Button type="button" variant="primary" loading={form.formState.isSubmitting} onClick={() => void decide("VERIFIED")}>Verify Payment</Button>
      </FormActions>
    </form>
  );
}
