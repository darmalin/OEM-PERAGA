import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/system/teams/new")({ component: NewTeam });

function NewTeam() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<{ name: string }>();
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const t = await call(api.POST("/api/v1/teams", { body: { name: v.name.trim() } }));
      void queryClient.invalidateQueries({ queryKey: ["teams"] });
      notifySuccess("Team added", "Add its members next.");
      await navigate({ to: "/system/teams/$teamId", params: { teamId: t.id } });
    } catch (e) {
      handleFormError(e, form.setError, ["name"]);
    }
  });
  return (
    <Page className="max-w-[860px]">
      <PageHead title="New Team" back={{ to: "/system/teams", label: "Teams" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Team">
            <Field label="Name" required className="max-w-md" error={form.formState.errors.name?.message}>{(p) => <Input {...p} {...form.register("name", { required: "Enter a name." })} />}</Field>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/system/teams">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Team</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
