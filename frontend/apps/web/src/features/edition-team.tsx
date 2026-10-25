import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";

import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Select } from "@/ui/input";
import { FormActions, Panel, PanelHeader } from "@/ui/page";

export const importRecipientsQuery = (editionId: string) => ({
  queryKey: ["import-recipients", editionId],
  queryFn: () => call(api.GET("/api/v1/visitor-leads/imports/recipients", { params: { query: { edition_id: editionId } } })),
});

/** The team that works this edition's leads; imports can share new leads among its callers. */
export function EditionTeamPanel({ editionId, manage }: { editionId: string; manage: boolean }) {
  const queryClient = useQueryClient();
  const id = useId();
  const teams = useQuery({ queryKey: ["teams"], queryFn: () => call(api.GET("/api/v1/teams")) });
  const current = useQuery({
    queryKey: ["edition-team", editionId],
    queryFn: () => call(api.GET("/api/v1/editions/{edition_id}/team", { params: { path: { edition_id: editionId } } })),
  });
  const recipients = useQuery(importRecipientsQuery(editionId));
  const [picked, setPicked] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const saved = current.data?.team_id ?? "";
  const value = picked ?? saved;
  const dirty = picked !== null && picked !== saved;

  const save = async () => {
    setSaving(true);
    try {
      const out = await call(api.PUT("/api/v1/editions/{edition_id}/team", { params: { path: { edition_id: editionId } }, body: { team_id: value || null } }));
      queryClient.setQueryData(["edition-team", editionId], out);
      setPicked(null);
      await queryClient.invalidateQueries({ queryKey: ["import-recipients", editionId] });
      notifySuccess("Team saved");
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };

  const names = recipients.data?.map((r) => r.full_name) ?? [];
  return (
    <Panel>
      <PanelHeader title="Team" />
      <div className="flex flex-col gap-4 px-5 py-4 text-[13px] max-md:px-4">
        <p className="text-muted">
          An import can share its new leads evenly among the members of this team who can make calls. Gate staff and other members without call access get none.
        </p>
        {teams.isError ? (
          <p className="text-label">You cannot see the team list.</p>
        ) : teams.isSuccess && teams.data.length === 0 ? (
          <p className="text-label">
            No teams yet. <Link to="/system/teams/new" className="text-link hover:underline">Create a team</Link> first.
          </p>
        ) : (
          <div className="flex max-w-sm flex-col gap-1.5">
            <label htmlFor={id} className="text-[13px] text-label">Team</label>
            <Select id={id} value={value} disabled={!manage || current.isPending} onChange={(e) => setPicked(e.target.value)}>
              <option value="">No team</option>
              {(teams.data ?? []).map((t) => {
                const n = t.member_ids?.length ?? 0;
                return (
                  <option key={t.id} value={t.id}>{t.name} · {n} {n === 1 ? "member" : "members"}</option>
                );
              })}
            </Select>
          </div>
        )}
        {recipients.isError ? null : (
          <p className={names.length ? "text-ink" : "text-label"} role="status">
            {recipients.isPending
              ? "Checking who receives leads"
              : names.length
                ? `Imported leads go to ${names.length} ${names.length === 1 ? "person" : "people"}: ${names.join(", ")}.`
                : "Nobody receives imported leads yet."}
            {dirty ? " Save to update." : ""}
          </p>
        )}
      </div>
      {manage ? (
        <FormActions>
          <Button variant="primary" disabled={!dirty} loading={saving} onClick={() => void save()}>
            Save Team
          </Button>
        </FormActions>
      ) : null}
    </Panel>
  );
}
