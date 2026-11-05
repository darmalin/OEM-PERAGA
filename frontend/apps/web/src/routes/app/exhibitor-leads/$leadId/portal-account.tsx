import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { exhibitorLeadQuery, portalAccountQuery } from "@/features/exhibitors/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/portal-account")({ component: PortalAccountStatus });

/** Disable or enable the exhibitor's portal account (one account for all its editions). */
function PortalAccountStatus() {
  const { leadId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const account = useQuery(portalAccountQuery(leadId));
  const [busy, setBusy] = useState(false);
  const a = account.data;
  const disable = a?.is_active ?? true;

  const save = async () => {
    if (!a) return;
    setBusy(true);
    try {
      const updated = await call(
        api.PUT("/api/v1/exhibitor-leads/{lead_id}/portal-account", { params: { path: { lead_id: leadId } }, body: { is_active: !a.is_active } }),
      );
      queryClient.setQueryData(portalAccountQuery(leadId).queryKey, updated);
      notifySuccess(updated.is_active ? "Portal account enabled" : "Portal account disabled", updated.email);
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId } });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page className="max-w-[800px]">
      <PageHead title={disable ? "Disable Portal Account" : "Enable Portal Account"} back={{ to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } }} />
      <Panel>
        {account.isPending ? <FormSkeleton /> : account.isError || !a ? <ErrorState error={account.error} onRetry={() => void account.refetch()} /> : (
          <>
            <Section title={a.email}>
              <ul className="max-w-2xl list-disc space-y-1 pl-5 text-[13px] text-muted">
                {disable ? (
                  <>
                    <li>The exhibitor is signed out at once and cannot sign in again.</li>
                    <li>The account is shared by every edition this exhibitor joins, so the portal closes for all of them.</li>
                    <li>An open invitation or password link stops working. Contract and payment records stay as they are.</li>
                  </>
                ) : (
                  <>
                    <li>The exhibitor can sign in again with the current password.</li>
                    <li>If they do not remember it, make a password reset link afterwards.</li>
                  </>
                )}
              </ul>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
              <Button variant={disable ? "danger" : "primary"} loading={busy} onClick={() => void save()}>{disable ? "Disable Account" : "Enable Account"}</Button>
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}
