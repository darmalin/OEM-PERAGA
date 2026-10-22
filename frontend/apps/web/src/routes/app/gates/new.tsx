import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/gates/new")({ component: NewGate });

function NewGate() {
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<{ code: string; name: string }>();
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const gate = await call(api.POST("/api/v1/gates", { body: { edition_id: edition.id, ...v } }));
      void queryClient.invalidateQueries({ queryKey: ["gates"] });
      notifySuccess("Gate added", gate.code);
      await navigate({ to: "/app/gates" });
    } catch (e) {
      handleFormError(e, form.setError, ["code", "name"]);
    }
  });
  return (
    <Page className="max-w-[860px]">
      <PageHead edition title="New Gate" meta={`In ${edition.code}.`} back={{ to: "/app/gates", label: "Gates" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Gate">
            <FieldGrid className="lg:grid-cols-2">
              <Field label="Code" required help="Short and unique in this edition, e.g. MAIN or HALL-B." error={form.formState.errors.code?.message}>
                {(p) => <Input {...p} className="uppercase" {...form.register("code", { required: "Enter a code." })} />}
              </Field>
              <Field label="Name" required error={form.formState.errors.name?.message}>
                {(p) => <Input {...p} placeholder="Main entrance" {...form.register("name", { required: "Enter a name." })} />}
              </Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/gates">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Gate</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
