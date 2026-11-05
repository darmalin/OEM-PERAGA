import { api, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { InvitationLink } from "@/features/exhibitors/invitation-link";
import { exhibitorLeadQuery, portalAccountQuery } from "@/features/exhibitors/queries";
import { useEditionById } from "@/lib/edition";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/invitation")({ component: NewInvitation });

/** A new one-time link: the invitation while the account has no password, a reset after. */
function NewInvitation() {
  const { leadId } = Route.useParams();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const account = useQuery(portalAccountQuery(leadId));
  const edition = useEditionById(lead.data?.edition_id);
  const [invitation, setInvitation] = useState<Schemas["InvitationOut"] | null>(null);
  const [busy, setBusy] = useState(false);
  const reset = account.data?.has_password ?? false;
  const create = async () => {
    setBusy(true);
    try {
      setInvitation(await call(api.POST("/api/v1/exhibitor-leads/{lead_id}/portal-invitation", { params: { path: { lead_id: leadId } } })));
      void queryClient.invalidateQueries({ queryKey: portalAccountQuery(leadId).queryKey });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  const title = reset ? "Password Reset Link" : "New Invitation Link";
  return (
    <Page className="max-w-[900px]">
      <PageHead title={title} back={{ to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } }} />
      <Panel>
        {lead.isPending || account.isPending ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} /> : account.isError ? <ErrorState error={account.error} /> : (
          <>
            <Section title={reset ? "Password Reset" : "Portal Invitation"}>
              {invitation ? (
                <InvitationLink invitation={invitation} email={account.data.email} timezone={edition?.timezone} />
              ) : reset ? (
                <p className="max-w-2xl text-[13px] text-muted">
                  For an exhibitor who forgot the portal password. The link lets {account.data.email} set a new password, works for 24 hours, and replaces any earlier link.
                  The current password keeps working until the new one is set.
                </p>
              ) : (
                <p className="max-w-2xl text-[13px] text-muted">
                  For an exhibitor who lost the link or let it expire. The new link replaces any earlier one.
                </p>
              )}
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>{invitation ? "Done" : "Cancel"}</Link></Button>
              {invitation ? null : <Button variant="primary" loading={busy} onClick={() => void create()}>Create Link</Button>}
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}
