import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";

import { CallVerificationFields, type MoveValues } from "@/features/leads/call-verification";
import { leadQuery } from "@/features/leads/queries";
import { useEditionById } from "@/lib/edition";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { outcomes, type TmStatus } from "@/lib/transitions";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";
import { FormActions } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

const VERIFICATION_FIELDS = ["lead_quality", "attend", "buyer_type", "b2b_matching"] as const;
const CALL_FIELDS = ["call_result", "called_at", "notes"] as const;

export function CallEditor({ leadId, to, onComplete, onCancel, onBusyChange, showHeading = true }: {
  leadId: string;
  to?: string;
  onComplete: () => void | Promise<void>;
  onCancel: () => void;
  onBusyChange?: (busy: boolean) => void;
  showHeading?: boolean;
}) {
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
      target: "", call_result: "", called_at: toLocalInput(new Date().toISOString(), tz), duration_minutes: "",
      notes: "", lead_quality: "", attend: "", buyer_type: "", b2b_matching: false,
    },
  });
  useEffect(() => { onBusyChange?.(form.formState.isSubmitting); }, [onBusyChange, form.formState.isSubmitting]);
  // The edition arrives with the lead; keep the initial call time in that edition's timezone.
  useEffect(() => {
    if (!form.getFieldState("called_at").isDirty) form.setValue("called_at", toLocalInput(new Date().toISOString(), tz));
  }, [tz, form]);
  const status = lead.data?.telemarketing_status;
  const choices = useMemo(() => (status ? outcomes(status) : []), [status]);
  const move = choices.find((c) => (c.answered ? "answered" : "unanswered") === form.watch("target"));
  const answered = move?.answered ?? false;

  // Show the stored Attend, buyer type, and B2B: kept on a call that is not answered, and the
  // starting point when it is. Lead Quality stays empty so it is always a conscious choice.
  const stored = lead.data;
  useEffect(() => {
    if (!stored) return;
    form.setValue("attend", stored.attend ?? "");
    form.setValue("buyer_type", stored.buyer_type ?? "");
    form.setValue("b2b_matching", stored.b2b_matching);
  }, [stored, form]);

  // A card dropped on a column preselects the outcome that leads there.
  useEffect(() => {
    const dropped = choices.find((c) => c.moves && c.to === to);
    if (dropped && !form.getValues("target")) form.setValue("target", dropped.answered ? "answered" : "unanswered");
  }, [choices, to, form]);
  const unansweredResults = (results.data ?? []).filter((r) => r !== "ANSWER");

  // An answered call is always Valid; preselect it so the agent only picks Attend.
  useEffect(() => {
    if (answered) form.setValue("lead_quality", "VALID");
  }, [answered, form]);

  const onSubmit = form.handleSubmit(async (v) => {
    if (!move) return form.setError("target", { message: "Choose the next status." });
    // Not answered: Lead Quality only, and none at all when the status stays and it is empty.
    const verification = move.answered
      ? { lead_quality: v.lead_quality as "VALID", attend: (v.attend || null) as never, buyer_type: (v.buyer_type || null) as never, b2b_matching: v.b2b_matching }
      : v.lead_quality
        ? { lead_quality: v.lead_quality }
        : undefined;
    try {
      const res = await call(
        api.POST("/api/v1/visitor-leads/{lead_id}/calls", {
          params: { path: { lead_id: leadId } },
          body: {
            call_result: move.answered ? "ANSWER" : v.call_result || "NO_ANSWER",
            called_at: fromLocalInput(v.called_at, tz),
            duration_seconds: v.duration_minutes ? Math.round(Number(v.duration_minutes) * 60) : null,
            notes: v.notes.trim() || null,
            verification,
          },
        }),
      );
      await queryClient.invalidateQueries({ predicate: (q) => ["lead", "leads", "calls", "verifications", "my-queue"].includes(String(q.queryKey[0])) });
      notifySuccess(
        move.moves
          ? `${lead.data?.first_name ?? "Lead"} moved to ${label("telemarketing_status", res.telemarketing_status)}`
          : `Call saved, ${lead.data?.first_name ?? "lead"} stays in ${label("telemarketing_status", res.telemarketing_status)}`,
        `Call #${res.call.attempt_number} saved${res.followup_id ? ", follow-up scheduled" : ""}.`,
      );
      await onComplete();
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

  return (
    <>
      {showHeading ? <div className="border-b border-line px-5 py-4 pr-14">
        <h2 className="text-[20px] font-semibold">{lead.data ? `Log Call for ${lead.data.first_name}` : "Log Call"}</h2>
        {lead.data ? <p className="mt-1 text-[13px] text-label tabular">{lead.data.registration_code} · {lead.data.phone ?? "no phone"} · now {label("telemarketing_status", lead.data.telemarketing_status)}</p> : null}
      </div> : null}
        {lead.isPending || results.isPending ? (
          <FormSkeleton />
        ) : lead.isError || results.isError ? (
          <ErrorState error={lead.error ?? results.error} onRetry={() => { void lead.refetch(); void results.refetch(); }} />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Call">
              <OutcomeChoice current={lead.data.telemarketing_status} choices={choices} register={form.register} error={form.formState.errors.target?.message} />
              <FieldGrid className="lg:grid-cols-2">
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
                <Field label="Notes" className="md:col-span-2" error={form.formState.errors.notes?.message}>
                  {(p) => <Textarea {...p} placeholder="What did the visitor say?" {...form.register("notes")} />}
                </Field>
              </FieldGrid>
            </Section>
            {move ? (
              <CallVerificationFields answered={answered} qualityRequired={answered || move.moves} register={form.register} control={form.control} errors={form.formState.errors} />
            ) : null}
            <FormActions>
              <Button type="button" variant="ghost" disabled={form.formState.isSubmitting} onClick={onCancel}>Cancel</Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>{move && !move.moves ? "Save Call" : "Save and Move"}</Button>
            </FormActions>
          </form>
        )}
    </>
  );
}

function OutcomeChoice({ current, choices, register, error }: {
  current: TmStatus;
  choices: { answered: boolean; to: TmStatus; moves: boolean }[];
  register: ReturnType<typeof useForm<MoveValues>>["register"];
  error?: string;
}) {
  return (
    <fieldset className="mb-5">
      <legend className="mb-2 text-[13px] text-label">
        Status change · Current: {label("telemarketing_status", current)}<span className="text-required" aria-hidden> *</span>
      </legend>
      <div className="flex flex-wrap gap-2">
        {choices.map((c) => (
          <label key={String(c.answered)} className="flex h-9 cursor-pointer items-center gap-2 rounded-[8px] bg-input px-3 text-[14px] has-[:checked]:bg-primary has-[:checked]:text-on-primary has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus pointer-coarse:h-11">
            <input type="radio" value={c.answered ? "answered" : "unanswered"} className="sr-only" {...register("target", { required: "Choose the next status." })} />
            {label("telemarketing_status", current)}{" "}
            <span className="text-[12px] opacity-70">
              to {label("telemarketing_status", c.to)}
              {!c.moves ? ` (${c.answered ? "Answered" : "Not answered"})` : ""}
            </span>
          </label>
        ))}
      </div>
      {error ? <p className="mt-1.5 text-[12px] text-required">{error}</p> : null}
    </fieldset>
  );
}
