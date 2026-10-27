import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { LINK_FIELDS, linkBody, LinkFields, linkValues, type LinkValues } from "@/features/campaigns/link-form";
import { campaignLinksQuery } from "@/features/campaigns/queries";
import { useEditionById } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/campaign-links/$linkId")({ component: EditLink });

function EditLink() {
  const { linkId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const links = useQuery(campaignLinksQuery(undefined));
  const link = links.data?.find((l) => l.id === linkId);
  const edition = useEditionById(link?.edition_id);
  const tz = edition?.timezone ?? "UTC";
  const form = useForm<LinkValues>({ values: link ? linkValues(link, tz) : undefined });

  const onSubmit = form.handleSubmit(async (v) => {
    if (!link) return;
    try {
      await call(api.PATCH("/api/v1/campaign-links/{link_id}", { params: { path: { link_id: linkId } }, body: { ...linkBody(v, tz), version: link.version } }));
      void queryClient.invalidateQueries({ queryKey: ["campaign-links"] });
      notifySuccess("Campaign link saved");
      await navigate({ to: "/app/editions/$editionId", params: { editionId: link.edition_id } });
    } catch (e) {
      handleFormError(e, form.setError, [...LINK_FIELDS]);
    }
  });

  return (
    <Page>
      <PageHead
        title={link?.name ?? "Campaign Link"}
        meta={link ? <span className="break-all">{link.url}</span> : null}
        back={link ? { to: "/app/editions/$editionId", params: { editionId: link.edition_id }, label: edition?.code ?? "Edition" } : { to: "/app/editions", label: "Editions" }}
      />
      <Panel>
        {links.isPending ? <FormSkeleton /> : !link || !edition ? <EmptyState title="Campaign link not found." /> : (
          <form onSubmit={onSubmit} noValidate>
            <LinkFields register={form.register} control={form.control} errors={form.formState.errors} timezone={tz} currentSourceId={link.lead_source_id} />
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/editions/$editionId" params={{ editionId: link.edition_id }}>Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Link</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
