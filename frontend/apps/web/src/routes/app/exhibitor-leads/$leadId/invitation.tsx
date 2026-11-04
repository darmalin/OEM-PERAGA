import { api, call, type Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { InvitationLink } from "@/features/exhibitors/invitation-link";
import { exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { useEditionById } from "@/lib/edition";
import { notifyError } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/invitation")({ component: NewInvitation });

function NewInvitation() {
  const { leadId } = Route.useParams();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const edition = useEditionById(lead.data?.edition_id);
  const [invitation, setInvitation] = useState<Schemas["InvitationOut"] | null>(null);
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      setInvitation(await call(api.POST("/api/v1/exhibitor-leads/{lead_id}/portal-invitation", { params: { path: { lead_id: leadId } } })));
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Page className="max-w-[900px]">
      <PageHead title="New Invitation Link" back={{ to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } }} />
      <Panel>
        {lead.isPending ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} /> : (
          <>
            <Section title="Portal Invitation">
              {invitation ? (
                <InvitationLink invitation={invitation} email={lead.data.email} timezone={edition?.timezone} />
              ) : (
                <p className="max-w-2xl text-[13px] text-muted">
                  For an exhibitor who lost the link or let it expire. The new link replaces any earlier one. Once {lead.data.email} has set a password, they sign in with it instead.
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
