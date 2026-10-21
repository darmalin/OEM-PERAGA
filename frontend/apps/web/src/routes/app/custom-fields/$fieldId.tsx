import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton, NoEdition } from "@/ui/states";

import { customFieldBody, CustomFieldFields, type CustomFieldValues } from "./-form";

export const Route = createFileRoute("/app/custom-fields/$fieldId")({ component: EditCustomField });

function EditCustomField() {
  const { fieldId } = Route.useParams();
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["custom-fields", edition?.id, "all"],
    enabled: Boolean(edition),
    queryFn: () => call(api.GET("/api/v1/visitor-custom-fields", { params: { query: { edition_id: edition!.id, include_inactive: true } } })),
  });
  const f = q.data?.find((x) => x.id === fieldId);
  const form = useForm<CustomFieldValues>({
    values: f ? { field_key: f.field_key, label: f.label, field_type: f.field_type, required: f.required, options: f.options.join("\n"), sort_order: String(f.sort_order), is_active: f.is_active, in_import: f.in_import, in_export: f.in_export } : undefined,
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    if (!f) return;
    try {
      await call(api.PATCH("/api/v1/visitor-custom-fields/{field_id}", { params: { path: { field_id: fieldId } }, body: { ...customFieldBody(v), version: f.version } }));
      void queryClient.invalidateQueries({ queryKey: ["custom-fields"] });
      notifySuccess("Custom field saved");
      await navigate({ to: "/app/custom-fields" });
    } catch (e) {
      handleFormError(e, form.setError, ["label", "options"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title={f?.label ?? "Custom Field"} back={{ to: "/app/custom-fields", label: "Custom Fields" }} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : !f ? <EmptyState title="This field is not in the selected edition." /> : (
          <form onSubmit={onSubmit} noValidate>
            <CustomFieldFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} creating={false} />
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/custom-fields">Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Custom Field</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
