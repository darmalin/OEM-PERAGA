import { api, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { PermissionMatrix } from "@/features/permission-matrix";
import { canGlobal, meQuery, useMe } from "@/lib/auth";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
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
          <RoleEditor key={role.permissions.join()} role={role} permissions={perms.data} editable={canGlobal(me, "role.manage")} />
        )}
      </Panel>
    </Page>
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
