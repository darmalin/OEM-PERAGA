import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

import { EMPTY_FORM, FORM_FIELDS, formBody, OrderFormFields, type FormValues } from "./-form";

export const Route = createFileRoute("/app/order-forms/new")({ component: NewOrderForm });

function NewOrderForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { edition } = useEdition();
  const form = useForm<FormValues>({ defaultValues: EMPTY_FORM });
  const onSubmit = form.handleSubmit(async (v) => {
    if (!edition) return;
    try {
      const created = await call(api.POST("/api/v1/order-forms", { body: { ...formBody(v), edition_id: edition.id, code: v.code.trim() } }));
      void queryClient.invalidateQueries({ queryKey: ["order-forms"] });
      notifySuccess(`Form ${created.code} added`, created.has_catalog ? "Add its catalog items next." : undefined);
      await navigate({ to: "/app/order-forms/$formId", params: { formId: created.id } });
    } catch (e) {
      handleFormError(e, form.setError, FORM_FIELDS);
    }
  });
  if (!edition) return <Page><NoEdition /></Page>;
  return (
    <Page className="max-w-[1000px]">
      <PageHead edition title="New Order Form" back={{ to: "/app/order-forms", label: "Order Forms" }} meta={`Adds to ${edition.code}. Publish it once its catalog or questions are ready.`} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <OrderFormFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} isNew />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/order-forms">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Form</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
