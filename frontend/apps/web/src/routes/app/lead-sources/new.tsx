import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

import { sourceBody, SourceFields, type SourceValues } from "./-form";

export const Route = createFileRoute("/app/lead-sources/new")({ component: NewSource });

function NewSource() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<SourceValues>({ defaultValues: { name: "", sort_order: "0", is_active: true } });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/lead-sources", { body: sourceBody(v) }));
      void queryClient.invalidateQueries({ queryKey: ["lead-sources"] });
      notifySuccess("Source added");
      await navigate({ to: "/app/lead-sources" });
    } catch (e) {
      handleFormError(e, form.setError, ["name", "sort_order"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="New Source" back={{ to: "/app/lead-sources", label: "Sources" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <SourceFields register={form.register} control={form.control} errors={form.formState.errors} />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/lead-sources">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Source</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
