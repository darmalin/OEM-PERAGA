import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";

import { useEdition } from "@/lib/edition";
import { formatDateTime } from "@/lib/format";
import { label } from "@/lib/labels";
import { Indicator } from "@/ui/indicator";
import { Facts, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/system/email-log/$jobId")({ component: EmailJob });

const EVENT_TONE: Record<string, string> = { SENT: "SENT", FAILED: "FAILED", CANCELLED: "CANCELLED", RETRY: "QUEUED", ATTEMPT: "SENDING", QUEUED: "QUEUED" };

function EmailJob() {
  const { jobId } = Route.useParams();
  const { editions } = useEdition();
  const q = useQuery({
    queryKey: ["email-jobs", jobId],
    queryFn: () => call(api.GET("/api/v1/email-jobs/{job_id}", { params: { path: { job_id: jobId } } })),
    refetchInterval: (query) => (query.state.data && ["QUEUED", "SENDING"].includes(query.state.data.status) ? 4000 : false),
  });
  const back = { to: "/system/email-log", label: "Email Log" };
  if (q.isPending) return <Page><PageHead title="Email" back={back} /><Panel><FormSkeleton /></Panel></Page>;
  if (q.isError) return <Page><PageHead title="Email" back={back} /><Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel></Page>;
  const j = q.data;
  const edition = editions.find((e) => e.id === j.edition_id);
  return (
    <Page className="max-w-[1100px]">
      <PageHead
        back={back}
        title={j.subject ?? label("email_kind", j.kind)}
        meta={<span>{label("email_kind", j.kind)} to {j.recipient}</span>}
        indicators={<Indicator value={j.status} group="email_status" />}
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Panel>
          <PanelHeader title="Delivery" />
          <ol className="flex flex-col divide-y divide-line px-5">
            {j.logs.map((l, i) => (
              <li key={`${l.occurred_at}-${i}`} className="flex flex-wrap items-center gap-3 py-3 text-[13px]">
                <span className="w-40 text-label tabular">{formatDateTime(l.occurred_at)}</span>
                <Indicator value={EVENT_TONE[l.event] ?? "QUEUED"} text={l.event.charAt(0) + l.event.slice(1).toLowerCase()} />
                {l.detail ? <span className="text-muted">{l.detail}</span> : null}
              </li>
            ))}
          </ol>
        </Panel>
        <Panel>
          <PanelHeader title="Details" />
          <div className="p-5">
            <Facts
              items={[
                ["To", j.recipient],
                ["Exhibition Type", edition ? edition.code : j.edition_id ? null : "System email"],
                ["Account", j.account_name ?? (j.attempts ? "Server settings" : null)],
                ["From", j.from_address],
                ["Attempts", String(j.attempts)],
                ["Queued", formatDateTime(j.queued_at)],
                ["Sent", j.sent_at ? formatDateTime(j.sent_at) : null],
                ["Error", j.error_summary],
                ["Message ID", j.provider_message_id ? <span key="m" className="break-all text-[12px]">{j.provider_message_id}</span> : null],
                ["Lead", j.visitor_lead_id ? <Link key="l" to="/app/visitor-leads/$leadId" params={{ leadId: j.visitor_lead_id }} className="text-link hover:underline">Open lead</Link> : null],
                ["Registration", j.registration_id ? <Link key="r" to="/app/registrations/$registrationId" params={{ registrationId: j.registration_id }} className="text-link hover:underline">Open registration</Link> : null],
              ]}
            />
          </div>
        </Panel>
      </div>
    </Page>
  );
}
