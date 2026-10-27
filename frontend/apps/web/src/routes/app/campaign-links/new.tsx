import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { emptyLink, LINK_FIELDS, linkBody, LinkFields, type LinkValues } from "@/features/campaigns/link-form";
import { useEditionById } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState } from "@/ui/states";

export const Route = createFileRoute("/app/campaign-links/new")({
  validateSearch: z.object({ edition: z.string() }),
  component: NewLink,
});

function NewLink() {
  const { edition: editionId } = Route.useSearch();
  const edition = useEditionById(editionId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<LinkValues>({ defaultValues: emptyLink });
  const back = { to: "/app/editions/$editionId", params: { editionId }, label: edition?.code ?? "Edition" } as const;

  const onSubmit = form.handleSubmit(async (v) => {
    if (!edition) return;
    try {
      const link = await call(api.POST("/api/v1/campaign-links", { body: { edition_id: editionId, ...linkBody(v, edition.timezone) } }));
      void queryClient.invalidateQueries({ queryKey: ["campaign-links"] });
      notifySuccess("Campaign link added", link.url);
      await navigate({ to: "/app/editions/$editionId", params: { editionId } });
    } catch (e) {
      handleFormError(e, form.setError, [...LINK_FIELDS]);
    }
  });

  return (
    <Page>
      <PageHead title="New Campaign Link" meta={edition ? `For ${edition.code}. Share the link; people who fill the form become leads of this edition.` : null} back={back} />
      <Panel>
        {!edition ? <EmptyState title="Edition not found." /> : (
          <form onSubmit={onSubmit} noValidate>
            <LinkFields register={form.register} control={form.control} errors={form.formState.errors} timezone={edition.timezone} />
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/editions/$editionId" params={{ editionId }}>Cancel</Link></Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Create Link</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
