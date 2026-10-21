import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useEdition } from "@/lib/edition";
import { fromLocalInput, formatDateTime, toLocalInput } from "@/lib/format";
import { handleFormError } from "@/lib/forms";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input, Textarea } from "@/ui/input";
import { ArrayBody } from "@/ui/list";
import { Facts, FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

export const Route = createFileRoute("/app/followups/$followupId")({ component: FollowupDetail });

type Action = "DONE" | "RESCHEDULE" | "CANCEL";
const ACTIONS: { v: Action; t: string }[] = [
  { v: "DONE", t: "Mark Done" },
  { v: "RESCHEDULE", t: "Reschedule" },
  { v: "CANCEL", t: "Cancel Follow-up" },
];

function FollowupDetail() {
  const { followupId } = Route.useParams();
  const { edition } = useEdition();
  const tz = edition?.timezone ?? "UTC";
  const queryClient = useQueryClient();
  const [action, setAction] = useState<Action>("DONE");
  const f = useQuery({
    queryKey: ["followup", followupId],
    queryFn: () => call(api.GET("/api/v1/followups/{followup_id}", { params: { path: { followup_id: followupId } } })),
  });
  const history = useQuery({
    queryKey: ["followup-history", followupId],
    queryFn: () => call(api.GET("/api/v1/followups/{followup_id}/history", { params: { path: { followup_id: followupId } } })),
  });
  const form = useForm<{ due_at: string; note: string }>({ defaultValues: { due_at: "", note: "" } });

  const submit = form.handleSubmit(async (v) => {
    if (!f.data) return;
    if (action === "RESCHEDULE" && !v.due_at) {
      form.setError("due_at", { message: "Choose the new time." });
      return;
    }
    try {
      const updated = await call(
        api.PATCH("/api/v1/followups/{followup_id}", {
          params: { path: { followup_id: followupId } },
          body: { version: f.data.version, action, due_at: action === "RESCHEDULE" ? fromLocalInput(v.due_at, tz) : null, note: v.note.trim() || null },
        }),
      );
      queryClient.setQueryData(["followup", followupId], updated);
      void history.refetch();
      void queryClient.invalidateQueries({ queryKey: ["followups"] });
      void queryClient.invalidateQueries({ queryKey: ["lead", updated.visitor_lead_id] });
      form.reset({ due_at: "", note: "" });
      notifySuccess(action === "DONE" ? "Follow-up done" : action === "RESCHEDULE" ? "Follow-up rescheduled" : "Follow-up cancelled");
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") void f.refetch();
      handleFormError(e, form.setError, ["due_at", "note"]);
    }
  });

  return (
    <Page className="max-w-[1100px]">
      <PageHead
        back={{ to: "/app/followups", label: "Follow-ups" }}
        title={f.data ? `Follow-up: ${f.data.lead_first_name ?? "Visitor"}` : "Follow-up"}
        meta={f.data ? <span className="tabular">Due {formatDateTime(f.data.due_at, tz)}</span> : null}
        indicators={f.data ? <Indicator value={f.data.status} group="followup_status" /> : null}
        actions={f.data ? <Button asChild><Link to="/app/visitor-leads/$leadId" params={{ leadId: f.data.visitor_lead_id }}>Open Lead</Link></Button> : null}
      />
      {f.isPending ? (
        <Panel><FormSkeleton /></Panel>
      ) : f.isError ? (
        <Panel><ErrorState error={f.error} onRetry={() => void f.refetch()} /></Panel>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Panel>
            {f.data.status === "OPEN" ? (
              <form onSubmit={submit} noValidate>
                <Section title="Update">
                  <div className="mb-5 flex flex-wrap gap-2" role="radiogroup" aria-label="Action">
                    {ACTIONS.map((a) => (
                      <label key={a.v} className="flex h-9 cursor-pointer items-center rounded-[8px] bg-input px-3 text-[14px] has-[:checked]:bg-primary has-[:checked]:text-on-primary has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus pointer-coarse:h-11">
                        <input type="radio" className="sr-only" checked={action === a.v} onChange={() => setAction(a.v)} />
                        {a.t}
                      </label>
                    ))}
                  </div>
                  <FieldGrid className="lg:grid-cols-2">
                    {action === "RESCHEDULE" ? (
                      <Field label="New Due At" required help={`Time in ${tz}. Current: ${toLocalInput(f.data.due_at, tz).replace("T", " ")}`} error={form.formState.errors.due_at?.message}>
                        {(p) => <Input {...p} type="datetime-local" {...form.register("due_at")} />}
                      </Field>
                    ) : null}
                    <Field label="Note" className="lg:col-span-2" error={form.formState.errors.note?.message}>
                      {(p) => <Textarea {...p} {...form.register("note")} />}
                    </Field>
                  </FieldGrid>
                </Section>
                <FormActions>
                  <Button type="submit" variant={action === "CANCEL" ? "danger" : "primary"} loading={form.formState.isSubmitting}>
                    {ACTIONS.find((a) => a.v === action)?.t}
                  </Button>
                </FormActions>
              </form>
            ) : (
              <div className="p-5 text-[14px] text-muted">This follow-up is {label("followup_status", f.data.status).toLowerCase()}. Create a new one from the lead if needed.</div>
            )}
          </Panel>
          <div className="flex flex-col gap-6">
            <Panel>
              <PanelHeader title="Details" />
              <div className="p-5">
                <Facts
                  items={[
                    ["Visitor", f.data.lead_first_name],
                    ["Registration ID", <span key="c" className="tabular">{f.data.lead_registration_code}</span>],
                    ["Note", f.data.note],
                    ["Completed", f.data.completed_at ? formatDateTime(f.data.completed_at, tz) : null],
                  ]}
                />
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="History" />
              <div className="p-5">
                <ArrayBody query={history} empty={<p className="text-[13px] text-muted">No changes yet.</p>}>
                  {(rows) => (
                    <ol className="flex flex-col gap-3 text-[13px]">
                      {rows.map((h, i) => (
                        <li key={i}>
                          <p className="font-medium">{label("followup_status", h.action) || h.action}</p>
                          <p className="text-label tabular">
                            {formatDateTime(h.created_at, tz)}
                            {h.new_due_at ? ` · due ${formatDateTime(h.new_due_at, tz)}` : ""}
                          </p>
                          {h.note ? <p className="text-muted">{h.note}</p> : null}
                        </li>
                      ))}
                    </ol>
                  )}
                </ArrayBody>
              </div>
            </Panel>
          </div>
        </div>
      )}
    </Page>
  );
}
