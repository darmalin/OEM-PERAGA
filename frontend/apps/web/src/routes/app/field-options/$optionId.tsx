import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton, NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/field-options/$optionId")({ component: EditOption });

function EditOption() {
  const { optionId } = Route.useParams();
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery({
    queryKey: ["field-options", edition?.id, "all", undefined],
    enabled: Boolean(edition),
    queryFn: () => call(api.GET("/api/v1/edition-field-options", { params: { query: { edition_id: edition!.id, include_inactive: true } } })),
  });
  const o = q.data?.find((x) => x.id === optionId);
  const form = useForm<{ label: string; sort_order: string; is_active: boolean }>({ values: o ? { label: o.label, sort_order: String(o.sort_order), is_active: o.is_active } : undefined });
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    if (!o) return;
    try {
      await call(api.PATCH("/api/v1/edition-field-options/{option_id}", { params: { path: { option_id: optionId } }, body: { version: o.version, label: v.label.trim(), sort_order: Number(v.sort_order || 0), is_active: v.is_active } }));
      void queryClient.invalidateQueries({ queryKey: ["field-options"] });
      notifySuccess("Option saved");
      await navigate({ to: "/app/field-options", search: { field: o.field } });
    } catch (e) {
      handleFormError(e, form.setError, ["label"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title={o ? `${label("option_field", o.field)}: ${o.label}` : "Field Option"} meta={o ? `Stored value ${o.value}` : null} back={{ to: "/app/field-options", label: "Field Options" }} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : !o ? <EmptyState title="This option is not in the selected edition." /> : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Option">
              <FieldGrid>
                <Field label="Label" required error={form.formState.errors.label?.message}>{(p) => <Input {...p} {...form.register("label", { required: "Enter a label." })} />}</Field>
                <Field label="Sort Order">{(p) => <Input {...p} type="number" {...form.register("sort_order")} />}</Field>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[13px] text-label">Status</span>
                  <label className="flex h-8 items-center gap-2 text-[14px]">
                    <Checkbox checked={form.watch("is_active")} onCheckedChange={(c) => form.setValue("is_active", c === true, { shouldDirty: true })} />
                    Offered on the lead form
                  </label>
                </div>
              </FieldGrid>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/field-options">Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Option</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
