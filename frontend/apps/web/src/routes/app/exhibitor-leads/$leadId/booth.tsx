import { ApiError, api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useState } from "react";

import { type BoothChoice, BoothPicker } from "@/features/exhibitors/booth-picker";
import { exhibitorLeadQuery } from "@/features/exhibitors/queries";
import { can, useMe } from "@/lib/auth";
import { formatMoney } from "@/lib/format";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/booth")({ component: ChooseBooth });

const AMOUNT = /^\d+(\.\d{1,2})?$/;

/** What is on the form: the lead's current booth, one picked from the list, or a new one. */
type Picked = { kind: "current" } | BoothChoice | null;

function ChooseBooth() {
  const { leadId } = Route.useParams();
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const l = lead.data;
  const canAdd = Boolean(l && can(me, "booth.manage"));
  // undefined: not touched yet, so the form shows the booth the lead holds at its agreed price.
  const [touched, setPicked] = useState<Picked | undefined>(undefined);
  const [priceText, setPrice] = useState<string | null>(null);
  const [fresh, setFresh] = useState({ hall: "", area: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const back = { to: "/app/exhibitor-leads/$leadId", label: l?.company_name ?? "Exhibitor lead", params: { leadId } };

  const picked: Picked = touched !== undefined ? touched : l?.booth_id ? { kind: "current" } : null;
  const price = priceText ?? (picked?.kind === "listed" ? picked.booth.price : picked?.kind === "current" ? (l?.booth_price ?? "") : "");

  const choose = (choice: BoothChoice) => {
    setErrors({});
    setPrice(null);
    if (choice.kind === "listed" && choice.booth.id === l?.booth_id) {
      setPicked({ kind: "current" });
      return;
    }
    setPicked(choice);
    if (choice.kind === "new") setFresh({ hall: "", area: "" });
  };

  const currency = picked?.kind === "listed" ? picked.booth.currency : picked?.kind === "current" ? (l?.booth_currency ?? "") : "";
  const listPrice = picked?.kind === "listed" ? picked.booth.price : picked?.kind === "current" ? l?.booth_list_price : null;
  const isNew = picked?.kind === "new";

  const save = async (release = false) => {
    if (!l) return;
    const errs: Record<string, string> = {};
    if (!release) {
      if (!AMOUNT.test(price)) errs.price = "Enter an amount, e.g. 45000000.";
      if (isNew && (!AMOUNT.test(fresh.area) || Number(fresh.area) <= 0)) errs.area = "Enter the area in m², e.g. 18.";
    }
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const body = release
      ? { booth_id: null, version: l.version }
      : picked?.kind === "new"
        ? { new_booth: { code: picked.code, hall: fresh.hall || null, area_sqm: fresh.area, price }, price, version: l.version }
        : { booth_id: picked?.kind === "listed" ? picked.booth.id : l.booth_id, price, version: l.version };
    setBusy(true);
    try {
      const updated = await call(api.PUT("/api/v1/exhibitor-leads/{lead_id}/booth", { params: { path: { lead_id: leadId } }, body }));
      queryClient.setQueryData(exhibitorLeadQuery(leadId).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["booths"] });
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", leadId, "contract"] });
      notifySuccess(release ? "Booth released" : `Booth ${updated.booth_code ?? ""} held at ${formatMoney(updated.booth_price, updated.booth_currency ?? "")}`, updated.company_name);
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId } });
    } catch (e) {
      if (e instanceof ApiError && e.code === "DUPLICATE_BOOTH_CODE") setErrors({ code: "This booth code is already in the list. Search for it instead." });
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };

  const unchanged = picked?.kind === "current" && price === (l?.booth_price ?? "");
  return (
    <Page className="max-w-[900px]">
      <PageHead title="Choose Booth" back={back} meta={l?.booth_code ? `Holds ${l.booth_code} at ${formatMoney(l.booth_price, l.booth_currency ?? "")} now.` : undefined} />
      <Panel>
        {lead.isPending ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} /> : l ? (
          <>
            <Section title="Booth">
              {l.booth_preference ? <p className="mb-3 text-[13px] text-muted">Asked for: {l.booth_preference}</p> : null}
              <Field label="Find a booth" help={canAdd ? "Free booths of this edition. A code that is not listed is added to Booths when you save." : "Free booths of this edition."}>
                {(p) => <BoothPicker editionId={l.edition_id} canAdd={canAdd} onPick={choose} inputId={p.id} describedBy={p["aria-describedby"]} />}
              </Field>
              {picked ? (
                <div className="mt-4 rounded-[8px] border border-line p-4 text-[13px]">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-[12px] text-label">{picked.kind === "new" ? "New booth" : picked.kind === "current" ? "Held now" : "Chosen booth"}</p>
                      <p className="text-[16px] font-semibold tabular">{picked.kind === "new" ? picked.code : picked.kind === "listed" ? picked.booth.code : l.booth_code}</p>
                      {picked.kind === "listed" ? <p className="text-muted">{[picked.booth.hall, `${Number(picked.booth.area_sqm)} m²`].filter(Boolean).join(" · ")}</p> : null}
                    </div>
                    {picked.kind !== "current" ? (
                      <Button variant="ghost" size="sm" aria-label="Clear the chosen booth" onClick={() => { setPicked(undefined); setPrice(null); setErrors({}); }}><X aria-hidden /></Button>
                    ) : null}
                  </div>
                  {isNew ? (
                    <FieldGrid className="mt-4">
                      <Field label="Hall">{(p) => <Input {...p} value={fresh.hall} maxLength={100} onChange={(e) => setFresh((f) => ({ ...f, hall: e.target.value }))} />}</Field>
                      <Field label="Area (m²)" required error={errors.area ?? errors.code}>
                        {(p) => <Input {...p} inputMode="decimal" value={fresh.area} onChange={(e) => setFresh((f) => ({ ...f, area: e.target.value }))} />}
                      </Field>
                    </FieldGrid>
                  ) : null}
                </div>
              ) : null}
            </Section>
            {picked ? (
              <Section title="Price">
                <FieldGrid>
                  <Field
                    label={currency ? `Agreed Price (${currency})` : "Agreed Price"}
                    required
                    error={errors.price}
                    help={listPrice ? `List price ${formatMoney(listPrice, currency)}. It goes into the contract at Convert; a Draft contract follows it.` : isNew ? "In the edition's currency. Also saved as the new booth's list price." : undefined}
                  >
                    {(p) => <Input {...p} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value.trim())} />}
                  </Field>
                </FieldGrid>
              </Section>
            ) : null}
            <FormActions>
              {l.booth_id && l.stage === "OPPORTUNITY" ? (
                <Button variant="danger" className="mr-auto" loading={busy} onClick={() => void save(true)}>Release {l.booth_code}</Button>
              ) : null}
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
              <Button variant="primary" disabled={!picked || unchanged} loading={busy} onClick={() => void save()}>
                {picked?.kind === "current" ? "Save Price" : "Hold Booth"}
              </Button>
            </FormActions>
          </>
        ) : null}
      </Panel>
    </Page>
  );
}
