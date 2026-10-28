import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useMe } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { handleFormError } from "@/lib/forms";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input } from "@/ui/input";
import { Facts, FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/system/users/$userId/")({ component: UserDetail });

function UserDetail() {
  const { userId } = Route.useParams();
  const me = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [changingAccess, setChangingAccess] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const u = useQuery({ queryKey: ["user", userId], queryFn: () => call(api.GET("/api/v1/users/{user_id}", { params: { path: { user_id: userId } } })) });
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const form = useForm<{ full_name: string }>({ values: u.data ? { full_name: u.data.full_name } : undefined });
  const passwordForm = useForm<{ password: string; confirm_password: string }>({ defaultValues: { password: "", confirm_password: "" } });
  const editionName = (id: string | null) => (id ? (me.editions.find((e) => e.id === id)?.code ?? "Another edition") : "All editions");

  const save = form.handleSubmit(async (v) => {
    if (!u.data) return;
    try {
      const updated = await call(api.PATCH("/api/v1/users/{user_id}", { params: { path: { user_id: userId } }, body: { version: u.data.version, ...v } }));
      queryClient.setQueryData(["user", userId], updated);
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      notifySuccess("User saved");
    } catch (e) {
      handleFormError(e, form.setError, ["full_name"]);
    }
  });

  const changePassword = passwordForm.handleSubmit(async ({ password }) => {
    if (!u.data) return;
    try {
      const updated = await call(api.PATCH("/api/v1/users/{user_id}", {
        params: { path: { user_id: userId } }, body: { version: u.data.version, password },
      }));
      queryClient.setQueryData(["user", userId], updated);
      passwordForm.reset();
      notifySuccess("Password changed", "Existing sessions were ended. Use the new password to sign in.");
      if (userId === me.user.id) {
        queryClient.clear();
        await navigate({ to: "/login" });
      }
    } catch (e) {
      handleFormError(e, passwordForm.setError, ["password"]);
    }
  });

  const changeAccess = async (isActive: boolean) => {
    if (!u.data || changingAccess) return;
    setChangingAccess(true);
    try {
      const updated = await call(api.PATCH("/api/v1/users/{user_id}", {
        params: { path: { user_id: userId } }, body: { version: u.data.version, is_active: isActive },
      }));
      queryClient.setQueryData(["user", userId], updated);
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      setConfirmDisable(false);
      notifySuccess(isActive ? "User enabled" : "User disabled", isActive ? "This user can sign in again." : "Existing sessions were ended. This user can no longer sign in.");
    } catch (e) {
      notifyError(e);
    } finally {
      setChangingAccess(false);
    }
  };

  const remove = async (assignmentId: string) => {
    try {
      await call(api.DELETE("/api/v1/users/{user_id}/role-assignments/{assignment_id}", { params: { path: { user_id: userId, assignment_id: assignmentId } } }));
      setConfirming(null);
      void queryClient.invalidateQueries({ queryKey: ["user", userId] });
      notifySuccess("Role removed");
    } catch (e) {
      notifyError(e);
    }
  };

  if (u.isPending) return <Page><PageHead title="User" back={{ to: "/system/users", label: "Users" }} /><Panel><FormSkeleton /></Panel></Page>;
  if (u.isError) return <Page><PageHead title="User" back={{ to: "/system/users", label: "Users" }} /><Panel><ErrorState error={u.error} /></Panel></Page>;
  const user = u.data;

  return (
    <Page>
      <PageHead
        back={{ to: "/system/users", label: "Users" }}
        title={user.full_name}
        meta={user.email}
        indicators={<Indicator value={user.is_active ? "ACTIVE" : "CLOSED"} text={user.is_active ? "Active" : "Disabled"} />}
        actions={<Button asChild variant="primary"><Link to="/system/users/$userId/roles/new" params={{ userId }}>Add Role</Link></Button>}
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader title="Roles and scopes" />
            {user.role_assignments.length === 0 ? (
              <EmptyState title="No roles yet. Without a role this user can sign in but sees nothing." action={<Button asChild variant="primary"><Link to="/system/users/$userId/roles/new" params={{ userId }}>Add Role</Link></Button>} />
            ) : (
              <ul className="divide-y divide-line">
                {user.role_assignments.map((a) => (
                  <li key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-[14px]">
                    <span>
                      <span className="font-medium">{a.role_code.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}</span>
                      <span className="text-label"> · {label("scope_type", a.scope_type)} · {editionName(a.edition_id)}{a.team_id ? ` · team ${teams.data?.find((t) => t.id === a.team_id)?.name ?? ""}` : ""}</span>
                    </span>
                    {confirming === a.id ? (
                      <span className="flex items-center gap-2">
                        <span className="text-[13px] text-muted">Remove this role?</span>
                        <Button size="sm" variant="danger" onClick={() => void remove(a.id)}>Remove</Button>
                        <Button size="sm" variant="ghost" onClick={() => setConfirming(null)}>Keep</Button>
                      </span>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => setConfirming(a.id)}>Remove</Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          <Panel>
            <form onSubmit={save} noValidate>
              <Section title="Profile">
                <FieldGrid className="lg:grid-cols-2">
                  <Field label="Full Name" required error={form.formState.errors.full_name?.message}>{(p) => <Input {...p} {...form.register("full_name", { required: "Enter a name." })} />}</Field>

                </FieldGrid>
              </Section>
              <FormActions>
                <Button type="submit" variant="primary" disabled={!form.formState.isDirty || changingAccess || passwordForm.formState.isSubmitting} loading={form.formState.isSubmitting}>Save User</Button>
              </FormActions>
            </form>
          </Panel>
          <Panel>
            <form onSubmit={changePassword} noValidate>
              <Section title="Change Password">
                <p className="mb-4 text-[13px] text-label">Set a new password for this user. All existing sessions will be ended.</p>
                <FieldGrid className="lg:grid-cols-2">
                  <Field label="New Password" required help="At least 8 characters. Avoid common passwords." error={passwordForm.formState.errors.password?.message}>
                    {(p) => <Input {...p} type="password" autoComplete="new-password" maxLength={1024} {...passwordForm.register("password", { required: "Enter a new password.", minLength: { value: 8, message: "Use at least 8 characters." } })} />}
                  </Field>
                  <Field label="Confirm New Password" required error={passwordForm.formState.errors.confirm_password?.message}>
                    {(p) => <Input {...p} type="password" autoComplete="new-password" maxLength={1024} {...passwordForm.register("confirm_password", { required: "Confirm the new password.", validate: (value) => value === passwordForm.getValues("password") || "Passwords do not match." })} />}
                  </Field>
                </FieldGrid>
              </Section>
              <FormActions>
                <Button type="submit" variant="primary" loading={passwordForm.formState.isSubmitting} disabled={changingAccess || form.formState.isSubmitting}>Change Password</Button>
              </FormActions>
            </form>
          </Panel>
          <Panel>
            <PanelHeader title="Sign-in Access" />
            <div className="flex flex-col gap-3 p-5">
              <p className="text-[13px] text-muted">{user.is_active ? "This user can sign in. Disabling ends their existing sessions and blocks sign-in." : "This user is disabled and cannot sign in. Enable access to allow sign-in again."}</p>
              {user.id === me.user.id ? <p className="text-[13px] text-label">You cannot disable your own account.</p> : null}
              {confirmDisable ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px]">Disable this user?</span>
                  <Button variant="danger" loading={changingAccess} onClick={() => void changeAccess(false)}>Confirm Disable</Button>
                  <Button variant="ghost" disabled={changingAccess} onClick={() => setConfirmDisable(false)}>Cancel</Button>
                </div>
              ) : (
                <div>
                  <Button variant={user.is_active ? "danger" : "primary"} disabled={user.id === me.user.id || passwordForm.formState.isSubmitting || form.formState.isSubmitting} loading={changingAccess} onClick={() => user.is_active ? setConfirmDisable(true) : void changeAccess(true)}>{user.is_active ? "Disable User" : "Enable User"}</Button>
                </div>
              )}
            </div>
          </Panel>
        </div>
        <Panel>
          <PanelHeader title="Account" />
          <div className="p-5">
            <Facts items={[
              ["Teams", user.team_ids.map((id) => teams.data?.find((t) => t.id === id)?.name).filter(Boolean).join(", ") || null],
              ["Last sign-in", user.last_login_at ? formatDateTime(user.last_login_at) : "Never"],
              ["Created", formatDateTime(user.created_at)],
            ]} />
          </div>
        </Panel>
      </div>
    </Page>
  );
}
