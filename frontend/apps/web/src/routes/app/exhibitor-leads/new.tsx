import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { emptyLead, ExhibitorLeadFields, LEAD_FIELDS, leadBody, type ExhibitorLeadValues } from "@/features/exhibitors/lead-form";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/new")({ component: NewExhibitorLead });

function NewExhibitorLead() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { edition, editions } = useEdition();
  const form = useForm<ExhibitorLeadValues>({ defaultValues: { ...emptyLead, edition_id: edition?.id ?? "" } });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const lead = await call(api.POST("/api/v1/exhibitor-leads", { body: { ...leadBody(v), edition_id: v.edition_id } }));
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      notifySuccess("Exhibitor lead added", lead.company_name);
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId: lead.id } });
    } catch (e) {
      handleFormError(e, form.setError, [...LEAD_FIELDS, "edition_id"]);
    }
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const errors = form.formState.errors;
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="New Exhibitor Lead" back={{ to: "/app/exhibitor-leads", label: "Exhibitor Leads" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <ExhibitorLeadFields
            register={form.register}
            errors={errors}
            edition={
              <Field label="Exhibition Type" required error={errors.edition_id?.message}>
                {(p) => (
                  <Select {...p} {...form.register("edition_id", { required: "Choose an exhibition type." })}>
                    {editions.map((e) => <option key={e.id} value={e.id}>{e.code} · {e.name}</option>)}
                  </Select>
                )}
              </Field>
            }
          />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/exhibitor-leads">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Exhibitor Lead</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
