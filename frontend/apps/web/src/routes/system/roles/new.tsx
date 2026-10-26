import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { PermissionMatrix } from "@/features/permission-matrix";
import { ORDER_HELP, ORDER_RULES } from "@/features/role-order";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/system/roles/new")({ component: NewRole });

function NewRole() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const perms = useQuery({ queryKey: ["permissions"], queryFn: () => call(api.GET("/api/v1/permissions")), staleTime: Infinity });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const form = useForm<{ code: string; name: string; description: string; sort_order: string }>({ defaultValues: { sort_order: "100" } });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const r = await call(api.POST("/api/v1/roles", { body: { code: v.code.trim().toUpperCase(), name: v.name.trim(), description: v.description.trim(), sort_order: Number(v.sort_order), permissions: [...selected] } }));
      void queryClient.invalidateQueries({ queryKey: ["roles"] });
      notifySuccess("Role added", r.name);
      await navigate({ to: "/system/roles/$roleId", params: { roleId: r.id } });
    } catch (e) {
      handleFormError(e, form.setError, ["code", "name", "description", "sort_order"]);
    }
  });
  return (
    <Page>
      <PageHead title="New Role" back={{ to: "/system/roles", label: "Roles" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Role">
            <FieldGrid>
              <Field label="Code" required help="Uppercase, e.g. REGISTRATION_DESK." error={form.formState.errors.code?.message}>{(p) => <Input {...p} className="uppercase" {...form.register("code", { required: "Enter a code." })} />}</Field>
              <Field label="Name" required error={form.formState.errors.name?.message}>{(p) => <Input {...p} {...form.register("name", { required: "Enter a name." })} />}</Field>
              <Field label="Description">{(p) => <Input {...p} {...form.register("description")} />}</Field>
              <Field label="No." required help={ORDER_HELP} error={form.formState.errors.sort_order?.message}>{(p) => <Input {...p} type="number" min={1} max={9999} inputMode="numeric" {...form.register("sort_order", ORDER_RULES)} />}</Field>
            </FieldGrid>
          </Section>
          <Section title={`Permissions (${selected.size})`}>
            {perms.data ? <PermissionMatrix permissions={perms.data} selected={selected} onChange={setSelected} /> : null}
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/system/roles">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Role</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
