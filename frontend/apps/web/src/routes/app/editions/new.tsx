import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { EditionFields, editionPayload, type EditionValues, EXHIBITOR_FIELDS, exhibitorValues } from "@/features/edition-form";
import { meQuery } from "@/lib/auth";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/editions/new")({
  validateSearch: z.object({ exhibition_id: z.string().optional() }),
  component: NewEdition,
});

function NewEdition() {
  const { exhibition_id } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<EditionValues>({
    defaultValues: {
      exhibition_id: exhibition_id ?? "", year: String(new Date().getFullYear() + 1), name: "", start_date: "", end_date: "", venue_id: "", country: "",
      city: "", timezone: "Asia/Jakarta", default_currency: "IDR", status: "DRAFT", email_sender_name: "", email_reply_to: "", email_account_id: "",
      scanner_cache_ttl_minutes: "", ...exhibitorValues(),
    },
  });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const ed = await call(api.POST("/api/v1/editions", { body: { ...editionPayload(v), exhibition_id: v.exhibition_id, year: Number(v.year) } as never }));
      // The edition switcher lists editions from /auth/me.
      await queryClient.invalidateQueries({ queryKey: meQuery.queryKey });
      void queryClient.invalidateQueries({ queryKey: ["editions"] });
      notifySuccess("Edition added", `${ed.code} starts as Draft.`);
      await navigate({ to: "/app/editions/$editionId", params: { editionId: ed.id } });
    } catch (e) {
      handleFormError(e, form.setError, ["exhibition_id", "year", "name", "start_date", "end_date", "timezone", "default_currency", "email_reply_to", "email_account_id", "scanner_cache_ttl_minutes", ...EXHIBITOR_FIELDS]);
    }
  });
  return (
    <Page>
      <PageHead title="New Edition" meta="The edition code is the exhibition code plus the year." back={{ to: "/app/editions", label: "Editions" }} />
      <form onSubmit={onSubmit} noValidate>
        <Panel>
          <EditionFields register={form.register} watch={form.watch} errors={form.formState.errors} creating />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/editions">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Edition</Button>
          </FormActions>
        </Panel>
      </form>
    </Page>
  );
}
