import { api, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import { InvitationLink } from "@/features/exhibitors/invitation-link";
import { boothsQuery, exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { useEditionById } from "@/lib/edition";
import { formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { Facts, FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/convert")({ component: Convert });

function Convert() {
  const { leadId } = Route.useParams();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const edition = useEditionById(lead.data?.edition_id);
  const booths = useQuery({ ...boothsQuery(lead.data?.edition_id ?? ""), enabled: Boolean(lead.data?.booth_id) });
  const [result, setResult] = useState<Schemas["ConvertOut"] | null>(null);
  const [busy, setBusy] = useState(false);
  const booth = booths.data?.items.find((b) => b.id === lead.data?.booth_id);
  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };

  const convert = async () => {
    if (!lead.data) return;
    setBusy(true);
    try {
      const out = await call(api.POST("/api/v1/exhibitor-leads/{lead_id}/convert", { params: { path: { lead_id: leadId } }, body: { version: lead.data.version } }));
      queryClient.setQueryData(exhibitorLeadQuery(leadId).queryKey, out.lead);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      notifySuccess("Converted to exhibitor", `Contract ${out.contract_number}`);
      setResult(out);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const toLead = <Button asChild variant={result ? "primary" : "ghost"}><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>{result ? "Open Exhibitor" : "Cancel"}</Link></Button>;
  return (
    <Page className="max-w-[900px]">
      <PageHead title={result ? "Converted" : "Convert to Exhibitor"} back={back} />
      <Panel>
        {lead.isPending ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} /> : result ? (
          <>
            <Section title={`Contract ${result.contract_number}`}>
              {result.invitation ? (
                <InvitationLink invitation={result.invitation} email={result.lead.email} timezone={edition?.timezone} />
              ) : (
                <p className="max-w-2xl text-[13px] text-muted">
                  {result.lead.email} already has a portal account from another edition. This edition now shows in their portal; no new link is needed.
                </p>
              )}
            </Section>
            <FormActions>{toLead}</FormActions>
          </>
        ) : lead.data.stage !== "OPPORTUNITY" || !lead.data.booth_id ? (
          <EmptyState title="Only an Opportunity that holds a booth can be converted." action={toLead} />
        ) : (
          <>
            <Section title={lead.data.company_name}>
              <Facts
                items={[
                  ["Contact", `${lead.data.contact_name} · ${lead.data.email}`],
                  ["Booth", lead.data.booth_code ?? null],
                  ["Booth Price", booth ? formatMoney(booth.price, booth.currency) : null],
                ]}
              />
              <ul className="mt-4 max-w-2xl list-disc space-y-1 pl-5 text-[13px] text-muted">
                <li>The lead becomes an Exhibitor and keeps its booth.</li>
                <li>A Draft contract is made with the next contract number and the booth price.</li>
                <li>A portal account is made for {lead.data.email}, with a one-time link to set its password.</li>
              </ul>
            </Section>
            <FormActions>
              {toLead}
              <Button variant="primary" loading={busy} onClick={() => void convert()}>Convert to Exhibitor</Button>
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}
