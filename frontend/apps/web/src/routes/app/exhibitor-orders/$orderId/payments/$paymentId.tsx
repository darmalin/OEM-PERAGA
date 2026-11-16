import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { exhibitorOrderQuery, type OrderPayment as Payment, orderPaymentsQuery } from "@/features/order-forms/queries";
import { PaymentProofs } from "@/features/exhibitors/payment-proofs";
import { can, useMe } from "@/lib/auth";
import { handleFormError } from "@/lib/forms";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Textarea } from "@/ui/input";
import { Facts, FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-orders/$orderId/payments/$paymentId")({ component: OrderPaymentDetail });

function OrderPaymentDetail() {
  const { orderId, paymentId } = Route.useParams();
  const order = useQuery(exhibitorOrderQuery(orderId));
  const q = useQuery(orderPaymentsQuery(orderId));
  const payment = q.data?.items.find((p) => p.id === paymentId);
  const currency = q.data?.currency ?? "";
  return (
    <Page className="max-w-[1000px]">
      <PageHead
        title={payment ? formatMoney(payment.amount, currency) : "Payment"}
        indicators={payment ? <Indicator value={payment.status} group="payment_status" /> : null}
        back={{ to: "/app/exhibitor-orders/$orderId", label: order.data ? `Order ${order.data.order_number ?? ""}` : "Order", params: { orderId } }}
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
                  ["Recorded", formatDateTime(payment.created_at)],
                  ...(payment.reviewed_at ? ([["Reviewed", formatDateTime(payment.reviewed_at)]] as [string, string][]) : []),
                ]}
              />
            </Section>
            <Proof orderId={orderId} payment={payment} />
            <Review orderId={orderId} payment={payment} />
          </>
        )}
      </Panel>
    </Page>
  );
}

function Proof({ orderId, payment }: { orderId: string; payment: Payment }) {
  const me = useMe();
  const queryClient = useQueryClient();
  return (
    <PaymentProofs
      url={`/api/v1/exhibitor-orders/${orderId}/payments/${payment.id}/proof`}
      payment={payment}
      editable={payment.status === "PENDING" && can(me, "exhibitor_payment.record")}
      onChanged={() => queryClient.invalidateQueries({ queryKey: orderPaymentsQuery(orderId).queryKey })}
      onRemove={(number, version) =>
        call(api.DELETE("/api/v1/exhibitor-orders/{order_id}/payments/{payment_id}/proof/{number}", { params: { path: { order_id: orderId, payment_id: payment.id, number }, query: { version } } }))
      }
    />
  );
}

function Review({ orderId, payment }: { orderId: string; payment: Payment }) {
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
          api.POST("/api/v1/exhibitor-orders/{order_id}/payments/{payment_id}/review", {
            params: { path: { order_id: orderId, payment_id: payment.id } },
            body: { decision, notes: v.notes.trim() || null, version: payment.version },
          }),
        );
        await queryClient.invalidateQueries({ queryKey: ["exhibitor-orders"] });
        notifySuccess(decision === "VERIFIED" ? "Payment verified" : "Payment rejected");
      } catch (e) {
        handleFormError(e, form.setError, ["notes"]);
      }
    })();

  return (
    <form onSubmit={(e) => e.preventDefault()} noValidate>
      <Section title="Review">
        <p className="mb-3 max-w-2xl text-[13px] text-muted">Check the amount against the bank statement or the cash received. Verified payments count toward the order total.</p>
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
