import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useMe } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { handleFormError } from "@/lib/forms";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
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
  const [confirming, setConfirming] = useState<string | null>(null);
  const u = useQuery({ queryKey: ["user", userId], queryFn: () => call(api.GET("/api/v1/users/{user_id}", { params: { path: { user_id: userId } } })) });
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const form = useForm<{ full_name: string; is_active: boolean }>({ values: u.data ? { full_name: u.data.full_name, is_active: u.data.is_active } : undefined });
  const editionName = (id: string | null) => (id ? (me.editions.find((e) => e.id === id)?.code ?? "Another edition") : "All editions");

  const save = form.handleSubmit(async (v) => {
    if (!u.data) return;
    try {
      const updated = await call(api.PATCH("/api/v1/users/{user_id}", { params: { path: { user_id: userId } }, body: { version: u.data.version, ...v } }));
      queryClient.setQueryData(["user", userId], updated);
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      notifySuccess(v.is_active ? "User saved" : "User deactivated", v.is_active ? undefined : "Their open sessions were ended.");
    } catch (e) {
      handleFormError(e, form.setError, ["full_name"]);
    }
  });

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
        indicators={<Indicator value={user.is_active ? "ACTIVE" : "CLOSED"} text={user.is_active ? "Active" : "Deactivated"} />}
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
                  <div className="flex flex-col gap-1.5">
                    <span className="text-[13px] text-label">Access</span>
                    <label className="flex h-8 items-center gap-2 text-[14px]">
                      <Checkbox checked={form.watch("is_active")} disabled={user.id === me.user.id} onCheckedChange={(c) => form.setValue("is_active", c === true, { shouldDirty: true })} />
                      Can sign in
                    </label>
                    {user.id === me.user.id ? <p className="text-[12px] text-label">You can't deactivate yourself.</p> : null}
                  </div>
                </FieldGrid>
              </Section>
              <FormActions>
                <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save User</Button>
              </FormActions>
            </form>
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
