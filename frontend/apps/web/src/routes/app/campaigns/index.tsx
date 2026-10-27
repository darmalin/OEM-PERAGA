import { createFileRoute, Link } from "@tanstack/react-router";
import { BarChart3, Plus } from "lucide-react";

import { CampaignHelp, CampaignLinkList } from "@/features/campaigns/campaign-links-panel";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { Button } from "@/ui/button";
import { Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/campaigns/")({ component: Campaigns });

function Campaigns() {
  const me = useMe();
  const { edition } = useEdition();
  if (!edition) return <Page><NoEdition /></Page>;
  const manage = can(me, "edition.manage");
  return (
    <Page>
      <PageHead
        edition
        title="Campaigns"
        meta={`Public registration links of ${edition.code}.`}
        actions={
          <>
            <Button asChild>
              <Link to="/app/campaign-dashboard"><BarChart3 aria-hidden />Dashboard</Link>
            </Button>
            {manage ? (
              <Button asChild variant="primary">
                <Link to="/app/campaign-links/new" search={{ edition: edition.id }}><Plus aria-hidden />Add Campaign Link</Link>
              </Button>
            ) : null}
          </>
        }
      />
      <Panel>
        <CampaignHelp />
        <CampaignLinkList editionId={edition.id} timezone={edition.timezone} manage={manage} />
      </Panel>
    </Page>
  );
}
