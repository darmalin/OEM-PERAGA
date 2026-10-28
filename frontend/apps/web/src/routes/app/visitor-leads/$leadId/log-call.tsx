import { useQuery } from "@tanstack/react-query";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { z } from "zod";

import { CallEditor } from "@/features/leads/call-editor";
import { leadQuery } from "@/features/leads/queries";
import { label } from "@/lib/labels";
import { Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/visitor-leads/$leadId/log-call")({
  validateSearch: z.object({ to: z.string().optional(), from: z.enum(["board"]).optional() }),
  beforeLoad: ({ params, search }) => {
    if (search.from === "board") {
      throw redirect({ to: "/app/visitor-leads/board", search: { call_lead: params.leadId, call_to: search.to }, replace: true });
    }
  },
  component: LogCall,
});

function LogCall() {
  const { leadId } = Route.useParams();
  const { to } = Route.useSearch();
  const navigate = useNavigate();
  const lead = useQuery(leadQuery(leadId));
  const backTo = { to: "/app/visitor-leads/$leadId", params: { leadId } } as const;
  const done = () => navigate(backTo);
  return (
    <Page className="max-w-[960px]">
      <PageHead title={lead.data ? `Log Call for ${lead.data.first_name}` : "Log Call"}
        meta={lead.data ? <span className="tabular">{lead.data.registration_code} · {lead.data.phone ?? "no phone"} · now {label("telemarketing_status", lead.data.telemarketing_status)}</span> : null}
        back={{ ...backTo, label: lead.data?.first_name ?? "Visitor lead" }} />
      <Panel><CallEditor leadId={leadId} to={to} onComplete={done} onCancel={() => void done()} showHeading={false} /></Panel>
    </Page>
  );
}
