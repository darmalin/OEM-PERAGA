import { api, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { PermissionMatrix } from "@/features/permission-matrix";
import { ORDER_HELP, ORDER_RULES } from "@/features/role-order";
import { canGlobal, meQuery, useMe } from "@/lib/auth";
import { handleFormError } from "@/lib/forms";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/system/roles/$roleId")({ component: Role });

function Role() {
  const { roleId } = Route.useParams();
  const me = useMe();
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => call(api.GET("/api/v1/roles")) });
  const perms = useQuery({ queryKey: ["permissions"], queryFn: () => call(api.GET("/api/v1/permissions")), staleTime: Infinity });
  const role = roles.data?.find((r) => r.id === roleId);
  return (
    <Page>
      <PageHead back={{ to: "/system/roles", label: "Roles" }} title={role?.name ?? "Role"} meta={role ? `${role.code}${role.description ? ` · ${role.description}` : ""}` : null} />
      <Panel>
        {roles.isPending || perms.isPending ? <FormSkeleton /> : !role || !perms.data ? <EmptyState title="Role not found." /> : (
          // Remount when the saved permissions change, so the editor starts from them.
          <>
            <RoleDetails key={`${role.name}|${role.description}|${role.sort_order}`} role={role} editable={canGlobal(me, "role.manage")} />
            <RoleEditor key={role.permissions.join()} role={role} permissions={perms.data} editable={canGlobal(me, "role.manage")} />
          </>
        )}
      </Panel>
    </Page>
  );
}

function RoleDetails({ role, editable }: { role: Schemas["RoleOut"]; editable: boolean }) {
  const queryClient = useQueryClient();
  const form = useForm<{ name: string; description: string; sort_order: string }>({
    defaultValues: { name: role.name, description: role.description, sort_order: String(role.sort_order) },
  });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.PATCH("/api/v1/roles/{role_id}", { params: { path: { role_id: role.id } }, body: { name: v.name.trim(), description: v.description.trim(), sort_order: Number(v.sort_order) } }));
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      notifySuccess("Role saved");
    } catch (e) {
      handleFormError(e, form.setError, ["name", "description", "sort_order"]);
    }
  });
  return (
    <form onSubmit={onSubmit} noValidate className="border-b border-line">
      <Section title="Role">
        <FieldGrid>
          <Field label="Name" required error={form.formState.errors.name?.message}>{(p) => <Input {...p} readOnly={!editable} {...form.register("name", { required: "Enter a name." })} />}</Field>
          <Field label="Description">{(p) => <Input {...p} readOnly={!editable} {...form.register("description")} />}</Field>
          <Field label="No." required help={ORDER_HELP} error={form.formState.errors.sort_order?.message}>{(p) => <Input {...p} type="number" min={1} max={9999} inputMode="numeric" readOnly={!editable} {...form.register("sort_order", ORDER_RULES)} />}</Field>
        </FieldGrid>
      </Section>
      {editable ? (
        <FormActions>
          <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Role</Button>
        </FormActions>
      ) : null}
    </form>
  );
}

function RoleEditor({ role, permissions, editable }: { role: Schemas["RoleOut"]; permissions: Schemas["PermissionOut"][]; editable: boolean }) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(() => new Set(role.permissions));
  const [busy, setBusy] = useState(false);
  const roleId = role.id;
  const dirty = selected.size !== role.permissions.length || role.permissions.some((p) => !selected.has(p));

  const save = async () => {
    setBusy(true);
    try {
      await call(api.PUT("/api/v1/roles/{role_id}/permissions", { params: { path: { role_id: roleId } }, body: { permissions: [...selected] } }));
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      void queryClient.invalidateQueries({ queryKey: meQuery.queryKey });
      notifySuccess("Permissions saved", "Users with this role get them on their next request.");
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Section title={`Permissions (${selected.size})`}>
        {!editable ? <p className="mb-4 text-[13px] text-label">You can view this role. Roles are shared by every edition, so only a Super Admin can change them.</p> : null}
        <PermissionMatrix permissions={permissions} selected={selected} onChange={setSelected} readOnly={!editable} />
      </Section>
      {editable ? (
        <FormActions>
          <Button variant="ghost" disabled={!dirty} onClick={() => setSelected(new Set(role.permissions))}>Discard Changes</Button>
          <Button variant="primary" disabled={!dirty} loading={busy} onClick={() => void save()}>Save Permissions</Button>
        </FormActions>
      ) : null}
    </>
  );
}
