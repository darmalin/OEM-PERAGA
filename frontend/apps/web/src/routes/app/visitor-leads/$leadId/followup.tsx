import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { leadQuery } from "@/features/leads/queries";
import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { fromLocalInput } from "@/lib/format";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/visitor-leads/$leadId/followup")({ component: NewFollowup });

function NewFollowup() {
  const { leadId } = Route.useParams();
  const me = useMe();
  const { edition } = useEdition();
  const tz = edition?.timezone ?? "UTC";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(leadQuery(leadId));
  const agents = useQuery({
    queryKey: ["agents", edition?.id],
    enabled: Boolean(edition) && can(me, "visitor.assign"),
    queryFn: () => call(api.GET("/api/v1/visitor-leads/assignable-agents", { params: { query: { edition_id: edition!.id } } })),
  });
  const form = useForm<{ due_at: string; assigned_to: string; note: string }>({
    defaultValues: { due_at: "", assigned_to: "", note: "" },
  });

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(
        api.POST("/api/v1/visitor-leads/{lead_id}/followups", {
          params: { path: { lead_id: leadId } },
          body: { due_at: fromLocalInput(v.due_at, tz)!, assigned_to: v.assigned_to || null, note: v.note.trim() || null },
        }),
      );
      await queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
      void queryClient.invalidateQueries({ queryKey: ["followups"] });
      notifySuccess("Follow-up scheduled");
      await navigate({ to: "/app/visitor-leads/$leadId", params: { leadId } });
    } catch (e) {
      handleFormError(e, form.setError, ["due_at", "assigned_to", "note"]);
    }
  });

  return (
    <Page className="max-w-[960px]">
      <PageHead
        title={lead.data ? `Follow-up for ${lead.data.first_name}` : "New Follow-up"}
        meta={lead.data?.registration_code}
        back={{ to: "/app/visitor-leads/$leadId", params: { leadId }, label: lead.data?.first_name ?? "Visitor lead" }}
      />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Follow-up">
            <FieldGrid>
              <Field label="Due At" required help={`Time in ${tz}.`} error={form.formState.errors.due_at?.message}>
                {(p) => <Input {...p} type="datetime-local" {...form.register("due_at", { required: "Choose when to follow up." })} />}
              </Field>
              <Field label="Assigned To" help={agents.data ? undefined : "You."} error={form.formState.errors.assigned_to?.message}>
                {(p) =>
                  agents.data ? (
                    <Select {...p} {...form.register("assigned_to")}>
                      <option value="">Me ({me.user.full_name})</option>
                      {agents.data.filter((a) => a.id !== me.user.id).map((a) => <option key={a.id} value={a.id}>{a.full_name}</option>)}
                    </Select>
                  ) : (
                    <Input {...p} value={me.user.full_name} readOnly className="text-muted" />
                  )
                }
              </Field>
              <Field label="Note" className="md:col-span-2 lg:col-span-3">
                {(p) => <Textarea {...p} placeholder="What should happen on this follow-up?" {...form.register("note")} />}
              </Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/visitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Schedule Follow-up</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
