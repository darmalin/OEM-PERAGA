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

import { customFieldBody, CustomFieldFields, type CustomFieldValues } from "./-form";

export const Route = createFileRoute("/app/custom-fields/new")({ component: NewCustomField });

function NewCustomField() {
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<CustomFieldValues>({ defaultValues: { field_key: "", label: "", field_type: "text", required: false, options: "", sort_order: "0", is_active: true, in_import: true, in_export: true } });
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/visitor-custom-fields", { body: { ...customFieldBody(v), edition_id: edition.id, field_key: v.field_key, field_type: v.field_type as "text", validation: {} } }));
      void queryClient.invalidateQueries({ queryKey: ["custom-fields"] });
      notifySuccess("Custom field added");
      await navigate({ to: "/app/custom-fields" });
    } catch (e) {
      handleFormError(e, form.setError, ["field_key", "label", "options"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead edition title="New Custom Field" meta={`For ${edition.code}.`} back={{ to: "/app/custom-fields", label: "Custom Fields" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <CustomFieldFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} creating />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/custom-fields">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Custom Field</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
