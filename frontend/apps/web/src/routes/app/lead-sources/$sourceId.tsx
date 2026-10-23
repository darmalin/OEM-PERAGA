import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { leadSourcesQuery } from "@/features/leads/queries";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton } from "@/ui/states";

import { sourceBody, SourceFields, type SourceValues } from "./-form";

export const Route = createFileRoute("/app/lead-sources/$sourceId")({ component: EditSource });

function EditSource() {
  const { sourceId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery(leadSourcesQuery(true));
  const source = q.data?.find((s) => s.id === sourceId);
  const form = useForm<SourceValues>({ values: source ? { name: source.name, sort_order: String(source.sort_order), is_active: source.is_active } : undefined });
  const onSubmit = form.handleSubmit(async (v) => {
    if (!source) return;
    try {
      await call(api.PATCH("/api/v1/lead-sources/{source_id}", { params: { path: { source_id: sourceId } }, body: { ...sourceBody(v), version: source.version } }));
      void queryClient.invalidateQueries({ queryKey: ["lead-sources"] });
      notifySuccess("Source saved");
      await navigate({ to: "/app/lead-sources" });
    } catch (e) {
      handleFormError(e, form.setError, ["name", "sort_order"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title={source?.name ?? "Source"} back={{ to: "/app/lead-sources", label: "Sources" }} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : !source ? <EmptyState title="Source not found." /> : (
          <form onSubmit={onSubmit} noValidate>
            <SourceFields register={form.register} control={form.control} errors={form.formState.errors} />
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/lead-sources">Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Source</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
