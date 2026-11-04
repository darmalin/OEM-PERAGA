import { ApiError, api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { boothsQuery, exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { can, useMe } from "@/lib/auth";
import { formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Section } from "@/ui/field";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/booth")({ component: ChooseBooth });

function ChooseBooth() {
  const { leadId } = Route.useParams();
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const booths = useQuery({ ...boothsQuery(lead.data?.edition_id ?? "", { available: true }), enabled: Boolean(lead.data) });
  const [choice, setChoice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };

  const save = async (boothId: string | null) => {
    if (!lead.data) return;
    setBusy(true);
    try {
      const updated = await call(
        api.PUT("/api/v1/exhibitor-leads/{lead_id}/booth", { params: { path: { lead_id: leadId } }, body: { booth_id: boothId, version: lead.data.version } }),
      );
      queryClient.setQueryData(exhibitorLeadQuery(leadId).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["booths"] });
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", leadId, "contract"] });
      notifySuccess(boothId ? `Booth ${updated.booth_code ?? ""} held` : "Booth released", updated.company_name);
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId } });
    } catch (e) {
      // Taken meanwhile by someone else: show the fresh list.
      if (e instanceof ApiError && e.code === "BOOTH_TAKEN") void booths.refetch();
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const l = lead.data;
  return (
    <Page className="max-w-[900px]">
      <PageHead title="Choose Booth" back={back} meta={l?.booth_code ? `Holds ${l.booth_code} now.` : undefined} />
      <Panel>
        {lead.isPending || (l && booths.isPending) ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} /> : booths.isError ? <ErrorState error={booths.error} onRetry={() => void booths.refetch()} /> : (
          <>
            <Section title="Available Booths">
              {l?.booth_preference ? <p className="mb-3 text-[13px] text-muted">Asked for: {l.booth_preference}</p> : null}
              {booths.data && booths.data.items.length > 0 ? (
                <fieldset>
                  <legend className="sr-only">Booth</legend>
                  <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {booths.data.items.map((b) => (
                      <li key={b.id}>
                        <label className="flex cursor-pointer items-start gap-3 rounded-[8px] border border-line p-3 text-[13px] hover:bg-subtle has-[:checked]:border-ink has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-[var(--focus)]">
                          <input type="radio" name="booth" value={b.id} className="mt-1 accent-[var(--ink)]" checked={choice === b.id} onChange={() => setChoice(b.id)} />
                          <span className="min-w-0">
                            <span className="block font-medium tabular">{b.code}</span>
                            <span className="block text-muted">{[b.hall, `${Number(b.area_sqm)} m²`].filter(Boolean).join(" · ")}</span>
                            <span className="block text-muted tabular">{formatMoney(b.price, b.currency)}</span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </fieldset>
              ) : (
                <EmptyState
                  title="No booth is free in this edition."
                  action={can(me, "booth.manage") ? <Button asChild><Link to="/app/booths/new">Add Booth</Link></Button> : undefined}
                />
              )}
            </Section>
            <FormActions>
              {l?.booth_id && l.stage === "OPPORTUNITY" ? (
                <Button variant="danger" className="mr-auto" loading={busy} onClick={() => void save(null)}>Release {l.booth_code}</Button>
              ) : null}
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
              <Button variant="primary" disabled={!choice} loading={busy} onClick={() => void save(choice)}>Hold Booth</Button>
            </FormActions>
          </>
        )}
      </Panel>
    </Page>
  );
}
