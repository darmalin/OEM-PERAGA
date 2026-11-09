import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { format } from "date-fns";
import { useForm } from "react-hook-form";

import { exhibitorOrderQuery, orderPaymentsQuery } from "@/features/order-forms/queries";
import { handleFormError } from "@/lib/forms";
import { formatMoney } from "@/lib/format";
import { options } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-orders/$orderId/payments/new")({ component: RecordOrderPayment });

interface Values {
  amount: string;
  paid_on: string;
  method: "BANK_TRANSFER" | "CASH" | "OTHER";
  reference: string;
  notes: string;
}

const FIELDS = ["amount", "paid_on", "method", "reference", "notes"] as const;

function RecordOrderPayment() {
  const { orderId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const order = useQuery(exhibitorOrderQuery(orderId));
  const payments = useQuery(orderPaymentsQuery(orderId));
  const form = useForm<Values>({ defaultValues: { amount: "", paid_on: format(new Date(), "yyyy-MM-dd"), method: "BANK_TRANSFER", reference: "", notes: "" } });
  const { errors, isSubmitting } = form.formState;
  const back = { to: "/app/exhibitor-orders/$orderId", label: order.data ? `Order ${order.data.order_number ?? ""}` : "Order", params: { orderId } };

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const payment = await call(
        api.POST("/api/v1/exhibitor-orders/{order_id}/payments", {
          params: { path: { order_id: orderId } },
          body: { amount: v.amount, paid_on: v.paid_on, method: v.method, reference: v.reference.trim() || null, notes: v.notes.trim() || null },
        }),
      );
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-orders"] });
      notifySuccess("Payment recorded", "Attach the proof, then verify it.");
      await navigate({ to: "/app/exhibitor-orders/$orderId/payments/$paymentId", params: { orderId, paymentId: payment.id } });
    } catch (e) {
      handleFormError(e, form.setError, FIELDS);
    }
  });

  const p = payments.data;
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="Record Payment" back={back} meta={p ? `Outstanding ${formatMoney(p.outstanding_amount, p.currency)} of ${formatMoney(p.total_amount, p.currency)}` : undefined} />
      <Panel>
        {payments.isPending ? <FormSkeleton /> : payments.isError ? <ErrorState error={payments.error} onRetry={() => void payments.refetch()} /> : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Payment">
              <FieldGrid>
                <Field label={`Amount (${payments.data.currency})`} required error={errors.amount?.message}>
                  {(f) => <Input {...f} inputMode="decimal" {...form.register("amount", { required: "Enter the amount paid.", pattern: { value: /^\d+(\.\d{1,2})?$/, message: "Enter an amount, e.g. 5000000." } })} />}
                </Field>
                <Field label="Paid On" required error={errors.paid_on?.message}>
                  {(f) => <Input {...f} type="date" {...form.register("paid_on", { required: "Enter the payment date." })} />}
                </Field>
                <Field label="Method" required error={errors.method?.message}>
                  {(f) => (
                    <Select {...f} {...form.register("method")}>
                      {options("payment_method").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </Select>
                  )}
                </Field>
                <Field label="Reference" help="Transfer number or receipt number." error={errors.reference?.message}>
                  {(f) => <Input {...f} {...form.register("reference")} />}
                </Field>
                <Field label="Notes" className="md:col-span-2" help="Internal; the exhibitor does not see it." error={errors.notes?.message}>
                  {(f) => <Textarea {...f} {...form.register("notes")} />}
                </Field>
              </FieldGrid>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-orders/$orderId" params={{ orderId }}>Cancel</Link></Button>
              <Button type="submit" variant="primary" loading={isSubmitting}>Record Payment</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
