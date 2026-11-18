import { api, call, type Schemas } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { CampaignLinksPanel } from "@/features/campaigns/campaign-links-panel";
import { DeletePanel } from "@/features/delete-panel";
import { EditionTeamPanel } from "@/features/edition-team";
import { EditionFields, editionPayload, type EditionValues, EXHIBITOR_FIELDS, exhibitorValues } from "@/features/edition-form";
import { can, meQuery, useMe } from "@/lib/auth";
import { forgetEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { EditionBand } from "@/ui/band";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/editions/$editionId")({ component: Edition });

function values(e: Schemas["EditionOut"]): EditionValues {
  return {
    exhibition_id: e.exhibition_id, year: String(e.year), name: e.name, start_date: e.start_date, end_date: e.end_date,
    venue_id: e.venue_id ?? "", country: e.country ?? "", city: e.city ?? "", timezone: e.timezone,
    default_currency: e.default_currency, status: e.status, email_sender_name: e.email_sender_name ?? "",
    email_reply_to: e.email_reply_to ?? "", email_account_id: e.email_account_id ?? "",
    scanner_cache_ttl_minutes: e.scanner_cache_ttl_minutes ? String(e.scanner_cache_ttl_minutes) : "",
    ...exhibitorValues(e),
  };
}

function Edition() {
  const { editionId } = Route.useParams();
  const me = useMe();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const ed = useQuery({
    queryKey: ["edition", editionId],
    queryFn: () => call(api.GET("/api/v1/editions/{edition_id}", { params: { path: { edition_id: editionId } } })),
  });
  const form = useForm<EditionValues>({ values: ed.data ? values(ed.data) : undefined });
  const manage = can(me, "edition.manage");
  const onSubmit = form.handleSubmit(async (v) => {
    if (!ed.data) return;
    try {
      const updated = await call(api.PATCH("/api/v1/editions/{edition_id}", { params: { path: { edition_id: editionId } }, body: { ...editionPayload(v), status: v.status, version: ed.data.version } as never }));
      queryClient.setQueryData(["edition", editionId], updated);
      await queryClient.invalidateQueries({ queryKey: meQuery.queryKey });
      void queryClient.invalidateQueries({ queryKey: ["editions"] });
      notifySuccess("Edition saved", updated.code);
    } catch (e) {
      handleFormError(e, form.setError, ["name", "start_date", "end_date", "timezone", "default_currency", "email_reply_to", "email_account_id", "scanner_cache_ttl_minutes", "status", ...EXHIBITOR_FIELDS]);
    }
  });
  const deleteEdition = async () => {
    if (!ed.data) return;
    await call(api.DELETE("/api/v1/editions/{edition_id}", { params: { path: { edition_id: editionId }, query: { version: ed.data.version } } }));
    forgetEdition(editionId);
    queryClient.removeQueries({ queryKey: ["edition", editionId] });
    await Promise.all([queryClient.invalidateQueries({ queryKey: meQuery.queryKey }), queryClient.invalidateQueries({ queryKey: ["editions"] })]);
    notifySuccess("Edition deleted", ed.data.code);
    await navigate({ to: "/app/editions" });
  };
  return (
    <Page>
      <PageHead back={{ to: "/app/editions", label: "Editions" }} title={ed.data ? ed.data.code : "Edition"} meta={ed.data ? `${ed.data.exhibition_code ?? ""} · registration IDs start with ${ed.data.registration_id_prefix}` : null} />
      {ed.isPending ? <Panel><FormSkeleton /></Panel> : ed.isError ? <Panel><ErrorState error={ed.error} /></Panel> : (
        <div className="flex flex-col gap-6">
          <EditionBand edition={ed.data} />
          <form onSubmit={onSubmit} noValidate>
            <Panel>
              <EditionFields register={form.register} watch={form.watch} errors={form.formState.errors} creating={false} readOnly={!manage} />
              {manage ? <FormActions><Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Edition</Button></FormActions> : null}
            </Panel>
          </form>
          <EditionTeamPanel editionId={editionId} manage={manage} />
          <CampaignLinksPanel editionId={editionId} timezone={ed.data.timezone} manage={manage} />
          {manage ? <DeletePanel title="Delete Edition" description="Only an edition with nothing linked to it can be deleted: no booths, leads, registrations, order forms, gates, campaign links, imports or role assignments. To keep its data, archive it instead." confirmText={`Permanently delete ${ed.data.code}?`} onDelete={deleteEdition} onStale={() => void ed.refetch()} /> : null}
        </div>
      )}
    </Page>
  );
}
