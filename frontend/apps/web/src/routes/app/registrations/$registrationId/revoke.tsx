import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, Section } from "@/ui/field";
import { Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/registrations/$registrationId/revoke")({ component: Revoke });

function Revoke() {
  const { registrationId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reg = useQuery({
    queryKey: ["registration", registrationId],
    queryFn: () => call(api.GET("/api/v1/visitor-registrations/{registration_id}", { params: { path: { registration_id: registrationId } } })),
  });
  const active = reg.data?.qr_status === "ACTIVE";
  const form = useForm<{ reason: string; reissue: boolean; send_email: boolean }>({ values: { reason: "", reissue: !active, send_email: true } });

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/visitor-registrations/{registration_id}/revoke-qr", { params: { path: { registration_id: registrationId } }, body: v }));
      void queryClient.invalidateQueries({ queryKey: ["registration", registrationId] });
      void queryClient.invalidateQueries({ queryKey: ["registrations"] });
      void queryClient.invalidateQueries({ queryKey: ["lead", reg.data?.visitor_lead_id] });
      notifySuccess(v.reissue ? "New QR issued" : "QR revoked", v.reissue && v.send_email ? "The new QR email is queued." : undefined);
      await navigate({ to: "/app/registrations/$registrationId", params: { registrationId } });
    } catch (e) {
      handleFormError(e, form.setError, ["reason"]);
    }
  });

  return (
    <Page className="max-w-[860px]">
      <PageHead
        title={active ? `Revoke QR for ${reg.data?.first_name ?? "visitor"}` : `Issue a new QR for ${reg.data?.first_name ?? "visitor"}`}
        meta={reg.data?.registration_code}
        back={{ to: "/app/registrations/$registrationId", params: { registrationId }, label: "Registration" }}
      />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title={active ? "Revoke" : "Reissue"}>
            <p className="mb-5 max-w-2xl text-[14px] text-muted">
              {active
                ? "The current QR stops working at every gate, including scanners that are offline once they sync. This is recorded in the audit log."
                : "The previous QR is already revoked. Issuing a new one gives the visitor a fresh code."}
            </p>
            <div className="flex max-w-xl flex-col gap-4">
              <Field label="Reason" required error={form.formState.errors.reason?.message}>
                {(p) => <Textarea {...p} placeholder="For example: phone lost, QR shared publicly" {...form.register("reason", { required: "Give a reason for the audit log." })} />}
              </Field>
              {active ? (
                <label className="flex items-center gap-2 text-[14px]">
                  <Checkbox checked={form.watch("reissue")} onCheckedChange={(c) => form.setValue("reissue", c === true)} />
                  Issue a new QR right away
                </label>
              ) : null}
              {form.watch("reissue") ? (
                <label className="flex items-center gap-2 text-[14px]">
                  <Checkbox checked={form.watch("send_email")} onCheckedChange={(c) => form.setValue("send_email", c === true)} />
                  Email the new QR to the visitor
                </label>
              ) : null}
            </div>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/registrations/$registrationId" params={{ registrationId }}>Cancel</Link></Button>
            <Button type="submit" variant={active && !form.watch("reissue") ? "danger" : "primary"} loading={form.formState.isSubmitting} disabled={!reg.data}>
              {active ? (form.watch("reissue") ? "Revoke and Issue New QR" : "Revoke QR") : "Issue New QR"}
            </Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
