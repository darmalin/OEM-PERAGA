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

export const Route = createFileRoute("/system/users/new")({ component: NewUser });

function NewUser() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<{ full_name: string; email: string; password: string }>();
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const u = await call(api.POST("/api/v1/users", { body: v }));
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      notifySuccess("User added", "Give them a role so they can work.");
      await navigate({ to: "/system/users/$userId", params: { userId: u.id } });
    } catch (e) {
      handleFormError(e, form.setError, ["full_name", "email", "password"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="New User" meta="Share the first password through a separate channel; the user can reset it from the sign-in page." back={{ to: "/system/users", label: "Users" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="User">
            <FieldGrid>
              <Field label="Full Name" required error={form.formState.errors.full_name?.message}>{(p) => <Input {...p} {...form.register("full_name", { required: "Enter a name." })} />}</Field>
              <Field label="Email" required error={form.formState.errors.email?.message}>{(p) => <Input {...p} type="email" autoComplete="off" {...form.register("email", { required: "Enter an email." })} />}</Field>
              <Field label="Password" required help="At least 12 characters." error={form.formState.errors.password?.message}>{(p) => <Input {...p} type="password" autoComplete="new-password" {...form.register("password", { required: "Enter a password.", minLength: { value: 12, message: "Use at least 12 characters." } })} />}</Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/system/users">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save User</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
