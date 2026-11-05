import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";

import { can, useMe } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Facts, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, Skeleton } from "@/ui/states";

import { type ExhibitorLead, portalAccountQuery } from "./queries";

/** Sidebar of an exhibitor: its portal account, password links, disable and enable. */
export function PortalAccountPanel({ lead, timezone }: { lead: ExhibitorLead; timezone?: string }) {
  const me = useMe();
  const q = useQuery(portalAccountQuery(lead.id));
  const manage = can(me, "exhibitor.invite");
  const a = q.data;
  return (
    <Panel>
      <PanelHeader title="Exhibitor Portal" />
      <div className="flex flex-col gap-3 p-5 text-[13px]">
        {q.isPending ? <Skeleton className="h-16 w-full" /> : q.isError || !a ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : (
          <>
            <Facts
              items={[
                [
                  "Account",
                  !a.is_active ? <Indicator key="s" value="INACTIVE" text="Disabled" /> : a.has_password ? <Indicator key="s" value="ACTIVE" text="Active" /> : <Indicator key="s" value="PENDING" text="Waiting for Password" />,
                ],
                ["Email", a.email],
                ["Last Sign-in", a.last_login_at ? formatDateTime(a.last_login_at, timezone) : null],
                ...(a.link_expires_at ? ([["Open Link", `Expires ${formatDateTime(a.link_expires_at, timezone)}`]] as [string, string][]) : []),
              ]}
            />
            {!a.is_active ? <p className="text-muted">The exhibitor cannot sign in to the portal, for any edition.</p> : null}
            {manage ? (
              <div className="flex flex-wrap gap-2">
                {a.is_active ? (
                  <Button asChild size="sm">
                    <Link to="/app/exhibitor-leads/$leadId/invitation" params={{ leadId: lead.id }}>{a.has_password ? "Password Reset Link" : "New Invitation Link"}</Link>
                  </Button>
                ) : null}
                <Button asChild size="sm" variant={a.is_active ? "danger" : "secondary"}>
                  <Link to="/app/exhibitor-leads/$leadId/portal-account" params={{ leadId: lead.id }}>{a.is_active ? "Disable Account" : "Enable Account"}</Link>
                </Button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </Panel>
  );
}
