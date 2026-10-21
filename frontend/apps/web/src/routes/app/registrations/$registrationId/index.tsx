import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { MailPlus } from "lucide-react";
import { useState } from "react";

import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { uuid } from "@/lib/forms";
import { formatDateTime } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Facts, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/registrations/$registrationId/")({ component: RegistrationDetail });

function RegistrationDetail() {
  const { registrationId } = Route.useParams();
  const me = useMe();
  const { edition } = useEdition();
  const tz = edition?.timezone;
  const queryClient = useQueryClient();
  const [resendKey, setResendKey] = useState(uuid);
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ["registration", registrationId],
    queryFn: () => call(api.GET("/api/v1/visitor-registrations/{registration_id}", { params: { path: { registration_id: registrationId } } })),
    // Follow the QR email while the worker is still sending it.
    refetchInterval: (query) => (query.state.data?.email_jobs.some((j) => j.status === "QUEUED" || j.status === "SENDING") ? 4000 : false),
  });

  const resend = async () => {
    setBusy(true);
    try {
      await call(api.POST("/api/v1/visitor-registrations/{registration_id}/resend-qr", { params: { path: { registration_id: registrationId }, header: { "Idempotency-Key": resendKey } } }));
      setResendKey(uuid());
      notifySuccess("QR email queued", "It reuses the same QR code.");
      void queryClient.invalidateQueries({ queryKey: ["registration", registrationId] });
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  if (q.isPending) return <Page><PageHead title="Registration" back={{ to: "/app/registrations", label: "Registrations" }} /><Panel><FormSkeleton /></Panel></Page>;
  if (q.isError) return <Page><PageHead title="Registration" back={{ to: "/app/registrations", label: "Registrations" }} /><Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel></Page>;
  const r = q.data;
  const active = r.qr_status === "ACTIVE";

  return (
    <Page>
      <PageHead
        back={{ to: "/app/registrations", label: "Registrations" }}
        title={r.first_name}
        meta={<span className="tabular">{r.registration_code} · registered {formatDateTime(r.registered_at, tz)} via {label("channel", r.channel)}</span>}
        indicators={<><Indicator value={r.status} group="registration_status" /><Indicator value={r.qr_status} group="qr_status" /></>}
        actions={
          <>
            <Button asChild><Link to="/app/visitor-leads/$leadId" params={{ leadId: r.visitor_lead_id }}>Open Lead</Link></Button>
            {can(me, "registration.resend_qr") ? (
              <>
                <Button asChild variant={active ? "danger" : "secondary"}>
                  <Link to="/app/registrations/$registrationId/revoke" params={{ registrationId }}>{active ? "Revoke QR" : "Issue New QR"}</Link>
                </Button>
                {active ? (
                  <Button variant="primary" onClick={() => void resend()} loading={busy}><MailPlus aria-hidden />Resend QR Email</Button>
                ) : null}
              </>
            ) : null}
          </>
        }
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel>
          <PanelHeader title="QR emails" />
          {r.email_jobs.length === 0 ? (
            <EmptyState title="No QR email was sent for this registration." />
          ) : (
            <ul className="divide-y divide-line">
              {r.email_jobs.map((j) => (
                <li key={j.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[14px] font-medium break-all">{j.recipient}</span>
                    <Indicator value={j.status} group="email_status" />
                  </div>
                  <p className="mt-1 text-[12px] text-label tabular">
                    Queued {formatDateTime(j.queued_at, tz)}
                    {j.sent_at ? ` · sent ${formatDateTime(j.sent_at, tz)}` : ""} · template v{j.template_version} · {j.attempts} {j.attempts === 1 ? "attempt" : "attempts"}
                  </p>
                  {j.error_summary ? <p className="mt-1 text-[13px] text-[var(--red-fg)]">{j.error_summary}</p> : null}
                  {j.logs.length > 0 ? (
                    <details className="mt-2 text-[12px]">
                      <summary className="cursor-pointer rounded-[4px] text-link select-none">Delivery log</summary>
                      <ol className="mt-2 flex flex-col gap-1">
                        {j.logs.map((l, i) => (
                          <li key={i} className="tabular text-muted">{formatDateTime(l.occurred_at, tz)} · {label("email_status", l.event)}{l.detail ? ` · ${l.detail}` : ""}</li>
                        ))}
                      </ol>
                    </details>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          <p className="border-t border-line px-5 py-3 text-[12px] text-label">Sent means the mail server accepted the email. Bounces are not tracked yet.</p>
        </Panel>
        <Panel>
          <PanelHeader title="QR credentials" />
          <ul className="divide-y divide-line">
            {r.credentials.map((c) => (
              <li key={c.id} className="px-5 py-3 text-[13px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="tabular text-label">Issued {formatDateTime(c.issued_at, tz)}</span>
                  <Indicator value={c.status} />
                </div>
                {c.revoked_at ? <p className="mt-1 text-muted">Revoked {formatDateTime(c.revoked_at, tz)}{c.revoke_reason ? `: ${c.revoke_reason}` : ""}</p> : null}
              </li>
            ))}
          </ul>
          <div className="border-t border-line px-5 py-3">
            <Facts items={[["Status", label("registration_status", r.status)], ["Version", String(r.version)]]} />
          </div>
        </Panel>
      </div>
    </Page>
  );
}
