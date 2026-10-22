import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { CallVerificationFields, type MoveValues } from "@/features/leads/call-verification";
import { leadQuery } from "@/features/leads/queries";
import { useEditionById } from "@/lib/edition";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { moves, type TmStatus } from "@/lib/transitions";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

/** `to`: the column a card was dropped on; `from`: return to the board after saving. */
export const Route = createFileRoute("/app/visitor-leads/$leadId/log-call")({
  validateSearch: z.object({ to: z.string().optional(), from: z.enum(["board"]).optional() }),
  component: LogCall,
});

const VERIFICATION_FIELDS = ["lead_quality", "attend", "buyer_type", "b2b_matching"] as const;
const CALL_FIELDS = ["call_result", "called_at", "notes", "next_followup_at"] as const;

function LogCall() {
  const { leadId } = Route.useParams();
  const { to, from } = Route.useSearch();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(leadQuery(leadId));
  const tz = useEditionById(lead.data?.edition_id)?.timezone ?? "UTC";
  const results = useQuery({
    queryKey: ["call-results"],
    queryFn: () => call(api.GET("/api/v1/telemarketing/call-results")),
    staleTime: Infinity,
  });
  const form = useForm<MoveValues>({
    defaultValues: {
      target: to ?? "", call_result: "", called_at: toLocalInput(new Date().toISOString(), tz), duration_minutes: "",
      notes: "", next_followup_at: "", lead_quality: "", attend: "", buyer_type: "", b2b_matching: false,
    },
  });
  const allowed = lead.data ? moves(lead.data.telemarketing_status) : [];
  const move = allowed.find((m) => m.to === form.watch("target"));
  const answered = move?.answered ?? false;
  const unansweredResults = (results.data ?? []).filter((r) => r !== "ANSWER");

  // An answered call is always Valid; preselect it so the agent only picks Attend.
  useEffect(() => {
    if (answered) form.setValue("lead_quality", "VALID");
  }, [answered, form]);

  const backTo = from === "board"
    ? ({ to: "/app/visitor-leads/board" } as const)
    : ({ to: "/app/visitor-leads/$leadId", params: { leadId } } as const);

  const onSubmit = form.handleSubmit(async (v) => {
    if (!move) return form.setError("target", { message: "Choose where the lead moves." });
    try {
      const res = await call(
        api.POST("/api/v1/visitor-leads/{lead_id}/calls", {
          params: { path: { lead_id: leadId } },
          body: {
            call_result: move.answered ? "ANSWER" : v.call_result || "NO_ANSWER",
            called_at: fromLocalInput(v.called_at, tz),
            duration_seconds: v.duration_minutes ? Math.round(Number(v.duration_minutes) * 60) : null,
            notes: v.notes.trim() || null,
            next_followup_at: fromLocalInput(v.next_followup_at, tz),
            verification: {
              lead_quality: v.lead_quality as "VALID",
              attend: (v.attend || null) as never,
              buyer_type: (v.buyer_type || null) as never,
              b2b_matching: v.b2b_matching,
            },
          },
        }),
      );
      await queryClient.invalidateQueries({ predicate: (q) => ["lead", "leads", "calls", "verifications", "my-queue"].includes(String(q.queryKey[0])) });
      notifySuccess(
        `${lead.data?.first_name ?? "Lead"} moved to ${label("telemarketing_status", res.telemarketing_status)}`,
        `Call #${res.call.attempt_number} saved${res.followup_id ? ", follow-up scheduled" : ""}.`,
      );
      await navigate(backTo);
    } catch (e) {
      if (e instanceof ApiError) {
        for (const [field, message] of Object.entries(e.fields)) {
          const name = field.replace(/^verification\./, "");
          if ((VERIFICATION_FIELDS as readonly string[]).includes(name) || (CALL_FIELDS as readonly string[]).includes(name)) {
            form.setError(name as keyof MoveValues, { type: "server", message });
          }
        }
      }
      notifyError(e);
    }
  });

  const title = lead.data ? `Log Call for ${lead.data.first_name}` : "Log Call";
  return (
    <Page className="max-w-[960px]">
      <PageHead
        title={title}
        meta={lead.data ? <span className="tabular">{lead.data.registration_code} · {lead.data.phone ?? "no phone"} · now {label("telemarketing_status", lead.data.telemarketing_status)}</span> : null}
        back={{ ...backTo, label: from === "board" ? "Board" : (lead.data?.first_name ?? "Visitor lead") }}
      />
      <Panel>
        {lead.isPending || results.isPending ? (
          <FormSkeleton />
        ) : lead.isError || results.isError ? (
          <ErrorState error={lead.error ?? results.error} />
        ) : allowed.length === 0 ? (
          <EmptyState
            title={`${label("telemarketing_status", lead.data.telemarketing_status)} is a final status. No more calls can be logged for this lead.`}
            action={<Button asChild><Link {...backTo}>Back</Link></Button>}
          />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Call">
              <MoveChoice current={lead.data.telemarketing_status} allowed={allowed} register={form.register} error={form.formState.errors.target?.message} />
              <FieldGrid>
                {move && !move.answered && unansweredResults.length > 1 ? (
                  <Field label="Call Result" help="Why the call was not answered.">
                    {(p) => (
                      <Select {...p} {...form.register("call_result")}>
                        {unansweredResults.map((r) => <option key={r} value={r}>{label("call_result", r)}</option>)}
                      </Select>
                    )}
                  </Field>
                ) : null}
                <Field label="Called At" required help={`Time in ${tz}.`} error={form.formState.errors.called_at?.message}>
                  {(p) => <Input {...p} type="datetime-local" {...form.register("called_at", { required: "Called At is required." })} />}
                </Field>
                <Field label="Duration (minutes)">
                  {(p) => <Input {...p} type="number" min={0} step="0.5" {...form.register("duration_minutes")} />}
                </Field>
                <Field label="Next Follow-up" help="Optional. Creates a follow-up for you." error={form.formState.errors.next_followup_at?.message}>
                  {(p) => <Input {...p} type="datetime-local" {...form.register("next_followup_at")} />}
                </Field>
                <Field label="Notes" className="md:col-span-2 lg:col-span-3" error={form.formState.errors.notes?.message}>
                  {(p) => <Textarea {...p} placeholder="What did the visitor say?" {...form.register("notes")} />}
                </Field>
              </FieldGrid>
            </Section>
            <CallVerificationFields answered={answered} register={form.register} control={form.control} errors={form.formState.errors} />
            <FormActions>
              <Button asChild variant="ghost"><Link {...backTo}>Cancel</Link></Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save and Move</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}

function MoveChoice({ current, allowed, register, error }: {
  current: TmStatus;
  allowed: { to: TmStatus; answered: boolean }[];
  register: ReturnType<typeof useForm<MoveValues>>["register"];
  error?: string;
}) {
  return (
    <fieldset className="mb-5">
      <legend className="mb-2 text-[13px] text-label">
        Move from {label("telemarketing_status", current)} to<span className="text-required" aria-hidden> *</span>
      </legend>
      <div className="flex flex-wrap gap-2">
        {allowed.map((m) => (
          <label key={m.to} className="flex h-9 cursor-pointer items-center gap-2 rounded-[8px] bg-input px-3 text-[14px] has-[:checked]:bg-primary has-[:checked]:text-on-primary has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus pointer-coarse:h-11">
            <input type="radio" value={m.to} className="sr-only" {...register("target", { required: "Choose where the lead moves." })} />
            {label("telemarketing_status", m.to)}
            <span className="text-[12px] opacity-70">{m.answered ? "answered" : "not answered"}</span>
          </label>
        ))}
      </div>
      {error ? <p className="mt-1.5 text-[12px] text-required">{error}</p> : null}
    </fieldset>
  );
}
