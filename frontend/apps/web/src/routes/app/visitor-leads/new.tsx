import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { emptyPerson, PERSON_FIELDS, personPayload, PersonFields, type PersonValues } from "@/features/leads/person-form";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/visitor-leads/new")({ component: NewLead });

function NewLead() {
  const { edition: current, editions } = useEdition();
  const [editionId, setEditionId] = useState(current?.id ?? "");
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<PersonValues>({ defaultValues: emptyPerson() });
  const edition = editions.find((e) => e.id === editionId) ?? current;

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
      <PageHead title="New Visitor Lead" meta="Registration ID and the QR code are issued when you save; the visitor can enter the gate right away." back={{ to: "/app/visitor-leads", label: "Visitor Leads" }} />
      <form onSubmit={onSubmit} noValidate>
        <Panel>
          <PersonFields
            editionId={edition.id}
            register={form.register}
            control={form.control}
            errors={form.formState.errors}
            exhibitionType={
              <Field label="Exhibition Type" required help="The edition this lead belongs to. Cannot be changed later.">
                {(p) => (
                  <Select {...p} value={edition.id} onChange={(e) => setEditionId(e.target.value)}>
                    {editions.map((e) => <option key={e.id} value={e.id}>{e.code} · {e.name}</option>)}
                  </Select>
                )}
              </Field>
            }
          />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/visitor-leads">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Visitor Lead</Button>
          </FormActions>
        </Panel>
      </form>
    </Page>
  );
}
