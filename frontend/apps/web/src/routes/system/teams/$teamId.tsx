import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Select } from "@/ui/input";
import { Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/system/teams/$teamId")({ component: Team });

function Team() {
  const { teamId } = Route.useParams();
  const queryClient = useQueryClient();
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const users = useQuery({ queryKey: ["users", "all-active"], queryFn: () => call(api.GET("/api/v1/users", { params: { query: { is_active: true, page_size: 500 } } })) });
  const team = teams.data?.find((t) => t.id === teamId);
  const members = (users.data?.items ?? []).filter((u) => team?.member_ids.includes(u.id));
  const others = (users.data?.items ?? []).filter((u) => !team?.member_ids.includes(u.id));

  const add = async () => {
    setBusy(true);
    try {
      await call(api.POST("/api/v1/teams/{team_id}/members", { params: { path: { team_id: teamId } }, body: { user_id: pick } }));
      setPick("");
      await queryClient.invalidateQueries({ queryKey: ["teams"] });
      notifySuccess("Member added");
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  const remove = async (userId: string) => {
    try {
      await call(api.DELETE("/api/v1/teams/{team_id}/members/{user_id}", { params: { path: { team_id: teamId, user_id: userId } } }));
      await queryClient.invalidateQueries({ queryKey: ["teams"] });
      notifySuccess("Member removed");
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <Page className="max-w-[1000px]">
      <PageHead back={{ to: "/system/teams", label: "Teams" }} title={team?.name ?? "Team"} meta={team ? `${team.member_ids.length} members` : null} />
      {teams.isPending ? <Panel><FormSkeleton /></Panel> : !team ? <Panel><EmptyState title="Team not found." /></Panel> : (
        <Panel>
          <PanelHeader title="Members" />
          <div className="flex flex-wrap items-end gap-2 border-b border-line px-5 py-4">
            <Field label="Add a member" className="min-w-[260px] flex-1">
              {(p) => (
                <Select {...p} value={pick} onChange={(e) => setPick(e.target.value)}>
                  <option value="">Choose a user</option>
                  {others.map((u) => <option key={u.id} value={u.id}>{u.full_name} · {u.email}</option>)}
                </Select>
              )}
            </Field>
            <Button variant="primary" disabled={!pick} loading={busy} onClick={() => void add()}>Add Member</Button>
          </div>
          {members.length === 0 ? <EmptyState title="No members yet." /> : (
            <ul className="divide-y divide-line">
              {members.map((u) => (
                <li key={u.id} className="flex items-center justify-between gap-3 px-5 py-3 text-[14px]">
                  <Link to="/system/users/$userId" params={{ userId: u.id }} className="hover:underline">{u.full_name} <span className="text-label">{u.email}</span></Link>
                  <Button size="sm" variant="ghost" onClick={() => void remove(u.id)}>Remove</Button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}
    </Page>
  );
}
