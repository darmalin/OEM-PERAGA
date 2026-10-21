import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { leadQuery } from "@/features/leads/queries";
import { notifyError, notifySuccess } from "@/lib/notify";
import { uuid } from "@/lib/forms";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/visitor-leads/$leadId/register")({ component: RegisterVisitor });

function RegisterVisitor() {
  const { leadId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const lead = useQuery(leadQuery(leadId));
  // One key per visit of this page: a double click or a retry never registers twice.
  const [key] = useState(uuid);
  const form = useForm<{ channel: "ADMIN" | "TELEMARKETING" | "API"; send_email: boolean }>({
    defaultValues: { channel: "ADMIN", send_email: true },
  });
  const hasEmail = Boolean(lead.data?.email);

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const reg = await call(
        api.POST("/api/v1/visitor-registrations", {
          params: { header: { "Idempotency-Key": key } },
          body: { visitor_lead_id: leadId, channel: v.channel, send_email: v.send_email && hasEmail },
        }),
      );
      await queryClient.invalidateQueries({ queryKey: ["lead", leadId] });
      void queryClient.invalidateQueries({ queryKey: ["registrations"] });
      notifySuccess("Visitor registered", v.send_email && hasEmail ? "The QR email is queued." : "QR issued; no email sent.");
      await navigate({ to: "/app/registrations/$registrationId", params: { registrationId: reg.id } });
    } catch (e) {
      notifyError(e);
    }
  });

  return (
    <Page className="max-w-[960px]">
      <PageHead
        title={lead.data ? `Register ${lead.data.first_name}` : "Register Visitor"}
        meta={lead.data ? <span className="tabular">{lead.data.registration_code} · {lead.data.email ?? "no email"}</span> : null}
        back={{ to: "/app/visitor-leads/$leadId", params: { leadId }, label: lead.data?.first_name ?? "Visitor lead" }}
      />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Registration">
            <p className="mb-5 max-w-2xl text-[14px] text-muted">
              Registering issues a QR code right away. The visitor shows it at the gate. The code holds no personal data.
            </p>
            <FieldGrid>
              <Field label="Channel" required>
                {(p) => (
                  <Select {...p} {...form.register("channel")}>
                    <option value="ADMIN">Admin</option>
                    <option value="TELEMARKETING">Telemarketing</option>
                    <option value="API">API</option>
                  </Select>
                )}
              </Field>
              <div className="flex flex-col gap-1.5">
                <span className="text-[13px] text-label">QR email</span>
                <label className="flex h-8 items-center gap-2 text-[14px]">
                  <Checkbox
                    checked={hasEmail && form.watch("send_email")}
                    disabled={!hasEmail}
                    onCheckedChange={(c) => form.setValue("send_email", c === true)}
                  />
                  Email the QR code
                </label>
                {!hasEmail ? <p className="text-[12px] text-label">This visitor has no email. Print or show the QR from the registration page.</p> : null}
              </div>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/visitor-leads/$leadId" params={{ leadId }}>Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting} disabled={!lead.data}>Register and Issue QR</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
