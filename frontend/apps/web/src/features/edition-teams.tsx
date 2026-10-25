import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { FormActions, Panel, PanelHeader } from "@/ui/page";

export const importRecipientsQuery = (editionId: string) => ({
  queryKey: ["import-recipients", editionId],
  queryFn: () => call(api.GET("/api/v1/visitor-leads/imports/recipients", { params: { query: { edition_id: editionId } } })),
});

/** Teams that work this edition's leads; imports can share new leads among their callers. */
export function EditionTeamsPanel({ editionId, manage }: { editionId: string; manage: boolean }) {
  const queryClient = useQueryClient();
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const current = useQuery({
    queryKey: ["edition-teams", editionId],
    queryFn: () => call(api.GET("/api/v1/editions/{edition_id}/teams", { params: { path: { edition_id: editionId } } })),
  });
  const recipients = useQuery(importRecipientsQuery(editionId));
  const [picked, setPicked] = useState<Set<string> | null>(null);
  const [saving, setSaving] = useState(false);
  const selected = picked ?? new Set(current.data?.team_ids ?? []);
  const dirty = picked !== null && [...picked].sort().join() !== [...(current.data?.team_ids ?? [])].sort().join();

  const toggle = (id: string, on: boolean) => {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };
  const save = async () => {
    setSaving(true);
    try {
      const out = await call(api.PUT("/api/v1/editions/{edition_id}/teams", { params: { path: { edition_id: editionId } }, body: { team_ids: [...selected] } }));
      queryClient.setQueryData(["edition-teams", editionId], out);
      setPicked(null);
      await queryClient.invalidateQueries({ queryKey: ["import-recipients", editionId] });
      notifySuccess("Teams saved");
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };

  const names = recipients.data?.map((r) => r.full_name) ?? [];
  return (
    <Panel>
      <PanelHeader title="Sales Teams" />
      <div className="flex flex-col gap-4 px-5 py-4 text-[13px] max-md:px-4">
        <p className="text-muted">
          An import can share its new leads evenly among the members of these teams who can make calls. Gate staff and other members without call access get none.
        </p>
        {teams.isError ? (
          <p className="text-label">You cannot see the team list.</p>
        ) : (teams.data ?? []).length === 0 && teams.isSuccess ? (
          <p className="text-label">
            No teams yet. <Link to="/system/teams/new" className="text-link hover:underline">Create a team</Link> first.
          </p>
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3" aria-label="Teams">
            {(teams.data ?? []).map((t) => (
              <li key={t.id}>
                <label className="flex items-center gap-2">
                  <Checkbox checked={selected.has(t.id)} disabled={!manage} onCheckedChange={(c) => toggle(t.id, c === true)} />
                  <span>{t.name}</span>
                  <span className="text-label tabular">· {t.member_ids?.length ?? 0} {(t.member_ids?.length ?? 0) === 1 ? "member" : "members"}</span>
                </label>
              </li>
            ))}
          </ul>
        )}
        {recipients.isError ? null : <p className={names.length ? "text-ink" : "text-label"} role="status">
          {recipients.isPending
            ? "Checking who receives leads"
            : names.length
              ? `Imported leads go to ${names.length} ${names.length === 1 ? "person" : "people"}: ${names.join(", ")}.`
              : "Nobody receives imported leads yet."}
          {dirty ? " Save to update." : ""}
        </p>}
      </div>
      {manage ? (
        <FormActions>
          <Button variant="primary" disabled={!dirty} loading={saving} onClick={() => void save()}>
            Save Teams
          </Button>
        </FormActions>
      ) : null}
    </Panel>
  );
}
