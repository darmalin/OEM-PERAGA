import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { teamMemberOptionsQuery, teamQuery, teamUsersQuery } from "@/features/teams/queries";
import { handleFormError } from "@/lib/forms";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/system/teams/$teamId")({ component: Team });

function Team() {
  const { teamId } = Route.useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const team = useQuery(teamQuery(teamId));
  const users = useQuery(teamUsersQuery);
  const memberOptions = useQuery({ ...teamMemberOptionsQuery, enabled: team.data?.is_active === true });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<"disable" | "delete" | null>(null);
  const [removeId, setRemoveId] = useState<string | null>(null);
  const form = useForm<{ name: string }>({ values: team.data ? { name: team.data.name } : undefined });
  const failure = (error: unknown) => {
    if (error instanceof ApiError && error.code === "VERSION_CONFLICT") void team.refetch();
    notifyError(error);
  };
  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["teams"] }), queryClient.invalidateQueries({ queryKey: ["team", teamId] }),
      queryClient.invalidateQueries({ queryKey: ["auth"] }), queryClient.invalidateQueries({ queryKey: ["import-recipients"] }),
      queryClient.invalidateQueries({ queryKey: ["agents"] }), queryClient.invalidateQueries({ queryKey: ["dashboard", "options"] }),
      queryClient.invalidateQueries({ queryKey: ["user"] }),
    ]);
  };
  const save = form.handleSubmit(async ({ name }) => {
    if (!team.data) return;
    try {
      const updated = await call(api.PATCH("/api/v1/teams/{team_id}", { params: { path: { team_id: teamId } }, body: { version: team.data.version, name: name.trim() } }));
      queryClient.setQueryData(["team", teamId], updated);
      form.reset({ name: updated.name });
      await invalidate(); notifySuccess("Team saved");
    } catch (error) { if (error instanceof ApiError && error.code === "VERSION_CONFLICT") void team.refetch(); handleFormError(error, form.setError, ["name"]); }
  });
  const changeAccess = async () => {
    if (!team.data) return;
    setBusy(true);
    try {
      const updated = await call(api.PATCH("/api/v1/teams/{team_id}", { params: { path: { team_id: teamId } }, body: { version: team.data.version, is_active: !team.data.is_active } }));
      queryClient.setQueryData(["team", teamId], updated);
      setConfirm(null); await invalidate(); notifySuccess(updated.is_active ? "Team enabled" : "Team disabled");
    } catch (error) { failure(error); } finally { setBusy(false); }
  };
  const deleteTeam = async () => {
    if (!team.data) return;
    setBusy(true);
    try {
      await call(api.DELETE("/api/v1/teams/{team_id}", { params: { path: { team_id: teamId }, query: { version: team.data.version } } }));
      queryClient.removeQueries({ queryKey: ["team", teamId] });
      await queryClient.invalidateQueries({ queryKey: ["teams"] });
      notifySuccess("Team deleted", "User accounts were kept."); await navigate({ to: "/system/teams" });
    } catch (error) { failure(error); } finally { setBusy(false); }
  };
  const add = async () => {
    setBusy(true);
    try {
      const updated = await call(api.POST("/api/v1/teams/{team_id}/members/batch", { params: { path: { team_id: teamId } }, body: { user_ids: [...selected] } }));
      queryClient.setQueryData(["team", teamId], updated);
      setSelected(new Set()); await invalidate(); notifySuccess("Members added");
    } catch (error) { failure(error); } finally { setBusy(false); }
  };
  const remove = async (userId: string) => {
    setBusy(true);
    try {
      await call(api.DELETE("/api/v1/teams/{team_id}/members/{user_id}", { params: { path: { team_id: teamId, user_id: userId } } }));
      setRemoveId(null); await invalidate(); notifySuccess("Member removed");
    } catch (error) { failure(error); } finally { setBusy(false); }
  };
  if (team.isPending) return <Page><PageHead title="Team" back={{ to: "/system/teams", label: "Teams" }} /><Panel><FormSkeleton /></Panel></Page>;
  if (team.isError) return <Page><PageHead title="Team" back={{ to: "/system/teams", label: "Teams" }} /><Panel><ErrorState error={team.error} onRetry={() => void team.refetch()} /></Panel></Page>;
  const current = team.data;
  const blocked = busy || form.formState.isSubmitting;
  const existing = new Set(current.member_ids);
  const byId = new Map((users.data ?? []).map(user => [user.id, user]));
  const candidates = (memberOptions.data ?? []).filter(user => user.is_active && !existing.has(user.id) && `${user.full_name} ${user.email}`.toLowerCase().includes(search.toLowerCase()));
  return <Page className="max-w-[1100px]">
    <PageHead back={{ to: "/system/teams", label: "Teams" }} title={current.name} meta={`${current.member_ids.length} members`} indicators={<Indicator value={current.is_active ? "ACTIVE" : "CLOSED"} text={current.is_active ? "Active" : "Disabled"} />} />
    <div className="flex flex-col gap-6">
      <Panel><form onSubmit={save} noValidate><Section title="Team Details"><Field label="Name" required className="max-w-md" error={form.formState.errors.name?.message}>{p => <Input {...p} maxLength={200} {...form.register("name", { required: "Enter a team name.", validate: value => Boolean(value.trim()) || "Enter a team name." })} />}</Field></Section><FormActions><Button type="submit" variant="primary" disabled={!form.formState.isDirty || blocked} loading={form.formState.isSubmitting}>Save Team</Button></FormActions></form></Panel>
      <Panel><PanelHeader title="Members" />
        {users.isPending ? <FormSkeleton /> : users.isError ? <ErrorState error={users.error} onRetry={() => void users.refetch()} /> : <>
          {current.member_ids.length ? <ul className="divide-y divide-line">{current.member_ids.map(id => {
            const user = byId.get(id);
            return <li key={id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 text-[13px]"><div>{user ? <Link to="/system/users/$userId" params={{ userId: id }} className="font-medium hover:underline">{user.full_name} <span className="font-normal text-label">{user.email}</span></Link> : <span className="text-label">User outside your scope</span>}{user && !user.is_active ? <span className="ml-2 text-label">Disabled user</span> : null}</div>{removeId === id ? <div className="flex items-center gap-2"><span>Remove from this team?</span><Button size="sm" variant="danger" disabled={blocked} onClick={() => void remove(id)}>Confirm Remove</Button><Button size="sm" variant="ghost" disabled={blocked} onClick={() => setRemoveId(null)}>Keep</Button></div> : <Button size="sm" variant="ghost" disabled={blocked || !user} onClick={() => setRemoveId(id)}>Remove</Button>}</li>;
          })}</ul> : <EmptyState title="No members yet. Select users below to build this team." />}
          <div className="border-t border-line p-5"><h3 className="text-[14px] font-semibold">Add Members</h3><p className="mt-1 mb-3 text-[13px] text-label">Only active Telemarketing Agents can join a team. Select several agents to add them together.</p>
            {!current.is_active ? <p className="text-[13px] text-label">Enable this team before adding members.</p> : memberOptions.isPending ? <FormSkeleton /> : memberOptions.isError ? <ErrorState error={memberOptions.error} onRetry={() => void memberOptions.refetch()} /> : <>
              <Input aria-label="Search users to add" type="search" placeholder="Search by name or email" className="mb-3 max-w-md" value={search} onChange={event => setSearch(event.target.value)} />
              <div className="max-h-[280px] overflow-y-auto rounded-[8px] border border-line">{candidates.length ? candidates.map(user => <div key={user.id} className="flex items-center gap-3 border-b border-line px-3 py-2.5 last:border-b-0"><Checkbox id={`member-${user.id}`} checked={selected.has(user.id)} disabled={blocked || (!selected.has(user.id) && selected.size >= 500)} onCheckedChange={checked => setSelected(prev => { const next = new Set(prev); if (checked === true) next.add(user.id); else next.delete(user.id); return next; })} /><label htmlFor={`member-${user.id}`} className="min-w-0 cursor-pointer text-[13px]"><span className="font-medium">{user.full_name}</span><span className="ml-2 break-all text-label">{user.email}</span></label></div>) : <p className="p-4 text-[13px] text-label">No eligible users match this search.</p>}</div>
              <div className="mt-3 flex items-center gap-3"><Button variant="primary" loading={busy} disabled={!selected.size || blocked} onClick={() => void add()}>Add Selected Members{selected.size ? ` (${selected.size})` : ""}</Button>{selected.size ? <Button variant="ghost" disabled={blocked} onClick={() => setSelected(new Set())}>Clear Selection</Button> : null}</div>
            </>}
          </div>
        </>}
      </Panel>
      <Panel><PanelHeader title="Team Access" /><div className="flex flex-col gap-3 p-5"><p className="text-[13px] text-muted">Disabling pauses team-based access and new assignments. Memberships are retained so the team can be enabled again.</p>{confirm === "disable" ? <div className="flex flex-wrap items-center gap-2"><span className="text-[13px]">Disable this team?</span><Button variant="danger" loading={busy} disabled={blocked} onClick={() => void changeAccess()}>Confirm Disable</Button><Button variant="ghost" disabled={blocked} onClick={() => setConfirm(null)}>Cancel</Button></div> : <div><Button variant={current.is_active ? "danger" : "primary"} disabled={blocked} onClick={() => current.is_active ? setConfirm("disable") : void changeAccess()}>{current.is_active ? "Disable Team" : "Enable Team"}</Button></div>}</div></Panel>
      <Panel><PanelHeader title="Delete Team" /><div className="flex flex-col gap-3 p-5"><p className="text-[13px] text-muted">Deleting removes the team and its memberships. User accounts and leads are kept. Remove exhibition and role assignments first if the team is still in use.</p>{confirm === "delete" ? <div className="flex flex-wrap items-center gap-2"><span className="text-[13px]">Permanently delete {current.name}?</span><Button variant="danger" loading={busy} disabled={blocked} onClick={() => void deleteTeam()}>Confirm Delete</Button><Button variant="ghost" disabled={blocked} onClick={() => setConfirm(null)}>Cancel</Button></div> : <div><Button variant="danger" disabled={blocked} onClick={() => setConfirm("delete")}>Delete Team</Button></div>}</div></Panel>
    </div>
  </Page>;
}
