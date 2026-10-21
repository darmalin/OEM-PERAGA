import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { leadQuery } from "@/features/leads/queries";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/visitor-leads/$leadId/log-call")({ component: LogCall });

interface Values {
  call_result: string;
  called_at: string;
  duration_minutes: string;
  notes: string;
  next_followup_at: string;
}

function LogCall() {
  const { leadId } = Route.useParams();
  const { edition } = useEdition();
  const tz = edition?.timezone ?? "UTC";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(leadQuery(leadId));
  const results = useQuery({
    queryKey: ["call-results"],
    queryFn: () => call(api.GET("/api/v1/telemarketing/call-results")),
    staleTime: Infinity,
  });
  const form = useForm<Values>({
    defaultValues: { call_result: "", called_at: toLocalInput(new Date().toISOString(), tz), duration_minutes: "", notes: "", next_followup_at: "" },
  });
  const back = { to: "/app/visitor-leads/$leadId", params: { leadId }, label: lead.data?.first_name ?? "Visitor lead" };

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const res = await call(
        api.POST("/api/v1/visitor-leads/{lead_id}/calls", {
          params: { path: { lead_id: leadId } },
          body: {
            call_result: v.call_result,
            called_at: fromLocalInput(v.called_at, tz),
            duration_seconds: v.duration_minutes ? Math.round(Number(v.duration_minutes) * 60) : null,
            notes: v.notes.trim() || null,
            next_followup_at: fromLocalInput(v.next_followup_at, tz),
          },
        }),
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lead", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["calls", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["my-queue"] }),
      ]);
      notifySuccess(
        `Call #${res.call.attempt_number} saved`,
        `Status is now ${label("telemarketing_status", res.telemarketing_status)}${res.followup_id ? ", follow-up scheduled" : ""}.`,
      );
      await navigate({ to: "/app/visitor-leads/$leadId", params: { leadId }, search: { tab: v.call_result === "ANSWER" ? "verification" : "calls" } });
    } catch (e) {
      handleFormError(e, form.setError, ["call_result", "called_at", "notes", "next_followup_at"]);
    }
  });

  return (
    <Page className="max-w-[960px]">
      <PageHead
        title={lead.data ? `Log Call for ${lead.data.first_name}` : "Log Call"}
        meta={lead.data ? <span className="tabular">{lead.data.registration_code} · {lead.data.phone ?? "no phone"} · attempt #{lead.data.call_attempts + 1}</span> : null}
        back={back}
      />
      <Panel>
        {lead.isPending || results.isPending ? (
          <FormSkeleton />
        ) : lead.isError || results.isError ? (
          <ErrorState error={lead.error ?? results.error} />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Call">
              <fieldset className="mb-5">
                <legend className="mb-2 text-[13px] text-label">
                  Call Result<span className="text-required" aria-hidden> *</span>
                </legend>
                <div className="flex flex-wrap gap-2">
                  {results.data.map((r) => (
                    <label key={r} className="flex h-9 cursor-pointer items-center gap-2 rounded-[8px] bg-input px-3 text-[14px] has-[:checked]:bg-primary has-[:checked]:text-on-primary has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus pointer-coarse:h-11">
                      <input type="radio" value={r} className="sr-only" {...form.register("call_result", { required: "Choose the call result." })} />
                      {label("call_result", r)}
                    </label>
                  ))}
                </div>
                {form.formState.errors.call_result ? <p className="mt-1.5 text-[12px] text-required">{form.formState.errors.call_result.message}</p> : null}
              </fieldset>
              <FieldGrid>
                <Field label="Called At" required help={`Time in ${tz}.`}>
                  {(p) => <Input {...p} type="datetime-local" {...form.register("called_at", { required: true })} />}
                </Field>
                <Field label="Duration (minutes)">
                  {(p) => <Input {...p} type="number" min={0} step="0.5" {...form.register("duration_minutes")} />}
                </Field>
                <Field label="Next Follow-up" help="Optional. Creates a follow-up for you.">
                  {(p) => <Input {...p} type="datetime-local" {...form.register("next_followup_at")} />}
                </Field>
                <Field label="Notes" className="md:col-span-2 lg:col-span-3" error={form.formState.errors.notes?.message}>
                  {(p) => <Textarea {...p} placeholder="What did the visitor say?" {...form.register("notes")} />}
                </Field>
              </FieldGrid>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/visitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Call</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
