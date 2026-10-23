import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { options } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/field-options/new")({
  validateSearch: z.object({ field: z.string().optional() }),
  component: NewOption,
});

function NewOption() {
  const { field } = Route.useSearch();
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<{ field: string; label: string; value: string; sort_order: string }>({ defaultValues: { field: field ?? "BUSINESS_TYPE", label: "", value: "", sort_order: "0" } });
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/edition-field-options", { body: { edition_id: edition.id, field: v.field as "BRANCH", label: v.label.trim(), value: (v.value || v.label).trim(), sort_order: Number(v.sort_order || 0), is_active: true } }));
      void queryClient.invalidateQueries({ queryKey: ["field-options"] });
      notifySuccess("Option added");
      await navigate({ to: "/app/field-options", search: { field: v.field } });
    } catch (e) {
      handleFormError(e, form.setError, ["label", "value"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead edition title="New Field Option" meta={`For ${edition.code}.`} back={{ to: "/app/field-options", label: "Field Options" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Option">
            <FieldGrid>
              <Field label="Field" required>
                {(p) => <Select {...p} {...form.register("field")}>{options("option_field").filter((o) => o.value !== "EXHIBITION_TYPE" && o.value !== "PRODUCT_CATEGORY").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</Select>}
              </Field>
              <Field label="Label" required error={form.formState.errors.label?.message}>{(p) => <Input {...p} {...form.register("label", { required: "Enter a label." })} />}</Field>
              <Field label="Stored value" help="Defaults to the label. Imports match on it; it cannot change later." error={form.formState.errors.value?.message}>{(p) => <Input {...p} {...form.register("value")} />}</Field>
              <Field label="Sort Order">{(p) => <Input {...p} type="number" {...form.register("sort_order")} />}</Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/field-options">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Option</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
