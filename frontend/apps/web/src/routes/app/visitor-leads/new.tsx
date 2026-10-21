import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { emptyPerson, PERSON_FIELDS, personPayload, PersonFields, type PersonValues } from "@/features/leads/person-form";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/visitor-leads/new")({ component: NewLead });

function NewLead() {
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<PersonValues>({ defaultValues: emptyPerson() });

  if (!edition) return <Page><NoEdition /></Page>;

  const onSubmit = form.handleSubmit(async (values) => {
    if (!values.email.trim() && !values.phone.trim()) {
      form.setError("email", { message: "Email or Phone is required." });
      form.setError("phone", { message: "Email or Phone is required." });
      return;
    }
    try {
      const body: Record<string, unknown> = { ...personPayload(values), edition_id: edition.id, source: "MANUAL", first_name: values.first_name.trim() };
      if (!body.lead_date) delete body.lead_date;
      const lead = await call(api.POST("/api/v1/visitor-leads", { body: body as never }));
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
      notifySuccess("Visitor lead added", lead.registration_code);
      await navigate({ to: "/app/visitor-leads/$leadId", params: { leadId: lead.id } });
    } catch (e) {
      handleFormError(e, form.setError, PERSON_FIELDS);
    }
  });

  return (
    <Page>
      <PageHead title="New Visitor Lead" meta={`Edition ${edition.code}. Registration ID is issued when you save.`} back={{ to: "/app/visitor-leads", label: "Visitor Leads" }} />
      <form onSubmit={onSubmit} noValidate>
        <Panel>
          <PersonFields editionId={edition.id} register={form.register} control={form.control} errors={form.formState.errors} />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/visitor-leads">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Visitor Lead</Button>
          </FormActions>
        </Panel>
      </form>
    </Page>
  );
}
