import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/exhibitions/new")({ component: NewExhibition });

function NewExhibition() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<{ code: string; name: string }>();
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const ex = await call(api.POST("/api/v1/exhibitions", { body: { code: v.code.trim().toUpperCase(), name: v.name.trim(), is_active: true } }));
      void queryClient.invalidateQueries({ queryKey: ["exhibitions"] });
      notifySuccess("Exhibition added", ex.code);
      await navigate({ to: "/app/exhibitions/$exhibitionId", params: { exhibitionId: ex.id } });
    } catch (e) {
      handleFormError(e, form.setError, ["code", "name"]);
    }
  });
  return (
    <Page className="max-w-[860px]">
      <PageHead title="New Exhibition" back={{ to: "/app/exhibitions", label: "Exhibitions" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Exhibition">
            <FieldGrid className="lg:grid-cols-2">
              <Field label="Code" required help="Prefix of edition codes, e.g. IBTE becomes IBTE2027." error={form.formState.errors.code?.message}>
                {(p) => <Input {...p} className="uppercase" {...form.register("code", { required: "Enter a code." })} />}
              </Field>
              <Field label="Name" required error={form.formState.errors.name?.message}>
                {(p) => <Input {...p} {...form.register("name", { required: "Enter a name." })} />}
              </Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/exhibitions">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Exhibition</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
