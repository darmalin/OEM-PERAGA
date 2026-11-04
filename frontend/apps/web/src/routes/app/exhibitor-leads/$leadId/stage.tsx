import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { exhibitorLeadQuery, STAGE_MOVES } from "@/features/exhibitors/queries";
import { handleFormError } from "@/lib/forms";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/stage")({
  validateSearch: z.object({ to: z.enum(["LEAD", "OPPORTUNITY", "LOST"]) }),
  component: ChangeStage,
});

const NOTES: Record<string, string> = {
  OPPORTUNITY: "The lead is qualified. You can then choose a booth for it and convert it to an exhibitor.",
  LEAD: "The lead goes back to Lead. A booth it holds is released.",
  LOST: "The lead is closed as lost and its booth, if any, is released. It can be reopened later.",
};

function ChangeStage() {
  const { leadId } = Route.useParams();
  const { to } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const form = useForm<{ lost_reason: string }>({ defaultValues: { lost_reason: "" } });
  const back = { to: "/app/exhibitor-leads/$leadId", label: lead.data?.company_name ?? "Exhibitor lead", params: { leadId } };

  const onSubmit = form.handleSubmit(async (v) => {
    if (!lead.data) return;
    try {
      const updated = await call(
        api.POST("/api/v1/exhibitor-leads/{lead_id}/stage", {
          params: { path: { lead_id: leadId } },
          body: { stage: to, lost_reason: to === "LOST" ? v.lost_reason.trim() : null, version: lead.data.version },
        }),
      );
      queryClient.setQueryData(exhibitorLeadQuery(leadId).queryKey, updated);
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      void queryClient.invalidateQueries({ queryKey: ["booths"] });
      notifySuccess(`Moved to ${label("sales_stage", to)}`, updated.company_name);
      await navigate({ to: "/app/exhibitor-leads/$leadId", params: { leadId } });
    } catch (e) {
      handleFormError(e, form.setError, ["lost_reason"]);
    }
  });

  const title = to === "LEAD" && lead.data?.stage === "LOST" ? "Reopen Lead" : `Move to ${label("sales_stage", to)}`;
  return (
    <Page className="max-w-[800px]">
      <PageHead title={title} back={back} />
      <Panel>
        {lead.isPending ? <FormSkeleton /> : lead.isError ? <ErrorState error={lead.error} onRetry={() => void lead.refetch()} /> : !(STAGE_MOVES[lead.data.stage] ?? []).includes(to) ? (
          <EmptyState title={`A lead in stage ${label("sales_stage", lead.data.stage)} cannot move to ${label("sales_stage", to)}.`} action={<Button asChild><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>Back to the Lead</Link></Button>} />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title={lead.data.company_name}>
              <p className="flex flex-wrap items-center gap-2 text-[13px] text-muted">
                <Indicator value={lead.data.stage} group="sales_stage" /> to <Indicator value={to} group="sales_stage" />
              </p>
              <p className="mt-3 max-w-xl text-[13px] text-muted">{NOTES[to]}</p>
              {to === "LOST" ? (
                <Field label="Lost Reason" required className="mt-4 max-w-xl" error={form.formState.errors.lost_reason?.message}>
                  {(p) => <Textarea {...p} {...form.register("lost_reason", { validate: (v) => v.trim() !== "" || "Say why the lead was lost." })} />}
                </Field>
              ) : null}
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/exhibitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
              <Button type="submit" variant={to === "LOST" ? "danger" : "primary"} loading={form.formState.isSubmitting}>{title}</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
