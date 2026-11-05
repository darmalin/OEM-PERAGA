import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { exhibitorLeadQuery, leadOwnersQuery } from "@/features/exhibitors/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/owner")({ component: AssignOwner });

const NONE = "";

/** Give the lead to a sales person of its edition, or leave it unassigned. */
function AssignOwner() {
  const { leadId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const owners = useQuery({ ...leadOwnersQuery(lead.data?.edition_id ?? ""), enabled: Boolean(lead.data) });
  const [choice, setChoice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const current = lead.data?.lead_owner_id ?? NONE;
  const value = choice ?? current;

  const save = async () => {
    if (!lead.data) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await call(
        api.PATCH("/api/v1/exhibitor-leads/{lead_id}", {
          params: { path: { lead_id: leadId } },
          body: { lead_owner_id: value || null, version: lead.data.version },
        }),
      );
      queryClient.setQueryData(exhibitorLeadQuery(leadId).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      notifySuccess(updated.lead_owner_name ? `Assigned to ${updated.lead_owner_name}` : "Lead unassigned", updated.company_name);
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId } });
    } catch (e) {
      if (e instanceof ApiError) setError(e.fields.lead_owner_id ?? null);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };
  return (
    <Page className="max-w-[800px]">
      <PageHead title={lead.data?.lead_owner_id ? "Reassign Lead" : "Assign Lead"} back={back} />
      <Panel>
        {lead.isPending || (lead.data && owners.isPending) ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} /> : owners.isError ? <ErrorState error={owners.error} onRetry={() => void owners.refetch()} /> : !owners.data?.can_assign ? (
          <EmptyState title="Only users who see every lead of this edition can change the owner." />
        ) : (
          <>
            <Section title={lead.data.company_name}>
              <p className="mb-4 max-w-xl text-[13px] text-muted">
                The owner works the lead. Sales with Own Leads access see only the leads they own. The list holds active users who can edit exhibitor leads in this edition.
              </p>
              <Field label="Lead Owner" className="max-w-md" error={error ?? undefined}>
                {(p) => (
                  <Select {...p} value={value} onChange={(e) => setChoice(e.target.value)}>
                    <option value={NONE}>Unassigned</option>
                    {owners.data.owners.map((o) => <option key={o.id} value={o.id}>{o.full_name} · {o.email}</option>)}
                  </Select>
                )}
              </Field>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
              <Button variant="primary" disabled={value === current} loading={busy} onClick={() => void save()}>Save Owner</Button>
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}
