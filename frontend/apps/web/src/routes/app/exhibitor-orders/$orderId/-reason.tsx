import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { exhibitorOrderQuery } from "@/features/order-forms/queries";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

/** Return to the exhibitor or cancel: both need a reason the exhibitor reads in the portal. */
export function ReasonPage({ orderId, kind }: { orderId: string; kind: "return" | "cancel" }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery(exhibitorOrderQuery(orderId));
  const form = useForm<{ reason: string }>({ defaultValues: { reason: "" } });
  const o = q.data;
  const back = { to: "/app/exhibitor-orders/$orderId", params: { orderId }, label: o ? `Order ${o.order_number ?? ""}` : "Order" };
  const returning = kind === "return";
  const field = returning ? "notes" : "reason";
  const onSubmit = form.handleSubmit(async (v) => {
    if (!o) return;
    try {
      const updated = returning
        ? await call(api.POST("/api/v1/exhibitor-orders/{order_id}/review", { params: { path: { order_id: orderId } }, body: { decision: "RETURNED", notes: v.reason.trim(), version: o.version } }))
        : await call(api.POST("/api/v1/exhibitor-orders/{order_id}/cancel", { params: { path: { order_id: orderId } }, body: { reason: v.reason.trim(), version: o.version } }));
      queryClient.setQueryData(exhibitorOrderQuery(orderId).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", updated.exhibitor_lead_id, "orders"] });
      notifySuccess(returning ? `Order ${updated.order_number ?? ""} returned to the exhibitor` : `Order ${updated.order_number ?? ""} cancelled`);
      await navigate({ to: "/app/exhibitor-orders/$orderId", params: { orderId } });
    } catch (e) {
      // The API names the field "notes" when returning and "reason" when cancelling.
      handleFormError(e, (_name, error) => form.setError("reason", error), [field]);
    }
  });
  const allowed = o ? (returning ? o.status === "SUBMITTED" : o.status !== "CANCELLED") : false;
  const cancelLink = <Button asChild variant="ghost"><Link to="/app/exhibitor-orders/$orderId" params={{ orderId }}>Back</Link></Button>;
  return (
    <Page className="max-w-[800px]">
      <PageHead title={returning ? "Return Order" : "Cancel Order"} back={back} meta={o ? `${o.company_name} · ${o.form_code} ${o.form_title}` : undefined} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : !allowed ? (
          <EmptyState title={returning ? "Only an order waiting for review can be returned." : "This order is already cancelled."} action={cancelLink} />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Reason">
              <p className="mb-4 max-w-2xl text-[13px] text-muted">
                {returning
                  ? "The exhibitor sees this in the portal, changes the order, and sends it again with the same number."
                  : "The order stays in the records as Cancelled and the exhibitor sees this reason. It cannot be reopened; the exhibitor can send a new order."}
              </p>
              <Field label={returning ? "What should the exhibitor change?" : "Reason"} required error={form.formState.errors.reason?.message}>
                {(p) => <Textarea {...p} rows={4} maxLength={2000} {...form.register("reason", { validate: (v) => v.trim().length > 0 || "Write the reason." })} />}
              </Field>
            </Section>
            <FormActions>
              {cancelLink}
              <Button type="submit" variant={returning ? "primary" : "danger"} loading={form.formState.isSubmitting}>{returning ? "Return to Exhibitor" : "Cancel Order"}</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
