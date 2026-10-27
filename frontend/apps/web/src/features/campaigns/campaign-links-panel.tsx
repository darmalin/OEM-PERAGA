import { api, call, downloadFile } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Copy, Pencil, Plus, QrCode, RefreshCw } from "lucide-react";
import { useState } from "react";

import { leadSourcesQuery } from "@/features/leads/queries";
import { formatDateTime, formatNumber } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, TableSkeleton } from "@/ui/states";

import { type CampaignLink, campaignLinksQuery } from "./queries";

/** Short help shown above campaign link lists. */
export function CampaignHelp() {
  return (
    <p className="border-b border-line px-5 py-3 text-[13px] text-muted max-md:px-4">
      Share a link on Instagram, WhatsApp, or a poster. People who fill its form become leads of this edition with the link&apos;s Source and campaign. Their QR is active at once; the QR email and the assignment stay manual. Test links in a private window, not one signed in here.
    </p>
  );
}

/** The links of one edition, with Copy Link, QR Code, Edit, and New URL. */
export function CampaignLinkList({ editionId, timezone, manage }: { editionId: string; timezone: string; manage: boolean }) {
  const q = useQuery(campaignLinksQuery(editionId));
  const sources = useQuery(leadSourcesQuery(true));
  const sourceName = (id: string | null | undefined) => sources.data?.find((s) => s.id === id)?.name;
  if (q.isPending) return <TableSkeleton rows={3} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (q.data.length === 0) return <EmptyState title="No campaign links yet." />;
  return (
    <ul className="divide-y divide-line">
      {q.data.map((link) => (
        <LinkRow key={link.id} link={link} sourceName={sourceName(link.lead_source_id)} timezone={timezone} manage={manage} />
      ))}
    </ul>
  );
}

/** Campaign links on the edition page; the full view is Marketing > Campaigns. */
export function CampaignLinksPanel({ editionId, timezone, manage }: { editionId: string; timezone: string; manage: boolean }) {
  return (
    <Panel>
      <PanelHeader
        title="Campaign Links"
        actions={
          manage ? (
            <Button asChild size="sm" variant="primary">
              <Link to="/app/campaign-links/new" search={{ edition: editionId }}><Plus aria-hidden />Add Campaign Link</Link>
            </Button>
          ) : null
        }
      />
      <CampaignHelp />
      <CampaignLinkList editionId={editionId} timezone={timezone} manage={manage} />
    </Panel>
  );
}

function period(link: CampaignLink, timezone: string): string | null {
  if (!link.starts_at && !link.ends_at) return null;
  const from = link.starts_at ? formatDateTime(link.starts_at, timezone) : "now";
  const to = link.ends_at ? formatDateTime(link.ends_at, timezone) : "no end";
  return `${from} to ${to}`;
}

function LinkRow({ link, sourceName, timezone, manage }: { link: CampaignLink; sourceName?: string; timezone: string; manage: boolean }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const when = period(link, timezone);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link.url);
      notifySuccess("Link copied", link.url);
    } catch {
      notifyError(new Error("Copy failed. Select the link and copy it by hand."));
    }
  };
  const newUrl = async () => {
    setBusy(true);
    try {
      await call(api.POST("/api/v1/campaign-links/{link_id}/new-url", { params: { path: { link_id: link.id } } }));
      await queryClient.invalidateQueries({ queryKey: ["campaign-links"] });
      notifySuccess("New link made", "The old link no longer works.");
      setConfirming(false);
    } catch (e) {
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-col gap-3 px-5 py-4 max-md:px-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="flex min-w-0 flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[14px] font-medium">{link.name}</span>
          <Indicator value={link.state} group="campaign_state" />
          {link.gtm_container_id ? (
            <span className="rounded-full bg-input px-2 py-0.5 text-[11px] text-muted" title="This form loads a Google Tag Manager container">
              GTM {link.gtm_container_id}
            </span>
          ) : null}
        </div>
        <code className="break-all text-[12px] text-muted">{link.url}</code>
        <p className="text-[12px] text-label">
          <span className="tabular text-ink">{formatNumber(link.submission_count)}</span>
          {link.max_submissions ? <span className="tabular"> of {formatNumber(link.max_submissions)}</span> : null} registered
          {sourceName ? ` · Source ${sourceName}` : ""}
          {when ? ` · ${when}` : ""}
        </p>
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
        <Button size="sm" onClick={() => void copy()}><Copy aria-hidden />Copy Link</Button>
        <Button size="sm" onClick={() => void downloadFile(`/api/v1/campaign-links/${link.id}/qr.png`, `qr-${link.name}.png`).catch(notifyError)}>
          <QrCode aria-hidden />QR Code
        </Button>
        {manage ? (
          <>
            <Button asChild size="sm" variant="ghost">
              <Link to="/app/campaign-links/$linkId" params={{ linkId: link.id }}><Pencil aria-hidden />Edit</Link>
            </Button>
            {confirming ? (
              <>
                <Button size="sm" variant="danger" loading={busy} onClick={() => void newUrl()}>Replace link? The old one stops</Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>Keep</Button>
              </>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}><RefreshCw aria-hidden />New URL</Button>
            )}
          </>
        ) : null}
      </div>
    </li>
  );
}
