import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

export const Route = createFileRoute("/app/devices/$deviceId/revoke")({ component: RevokeDevice });

function RevokeDevice() {
  const { deviceId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<{ reason: string }>();
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/gate/devices/{device_id}/revoke", { params: { path: { device_id: deviceId } }, body: v }));
      void queryClient.invalidateQueries({ queryKey: ["devices"] });
      notifySuccess("Device revoked", "It can no longer scan or sync.");
      await navigate({ to: "/app/devices/$deviceId", params: { deviceId } });
    } catch (e) {
      handleFormError(e, form.setError, ["reason"]);
    }
  });
  return (
    <Page className="max-w-[860px]">
      <PageHead title="Revoke Scanner Device" back={{ to: "/app/devices/$deviceId", params: { deviceId }, label: "Device" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Revoke">
            <p className="mb-5 max-w-2xl text-[14px] text-muted">The device stops scanning at once. Scans it queued offline are refused when it tries to sync. This cannot be undone; register the device again to reuse it.</p>
            <Field label="Reason" required className="max-w-xl" error={form.formState.errors.reason?.message}>
              {(p) => <Textarea {...p} placeholder="For example: phone lost at Gate A" {...form.register("reason", { required: "Give a reason for the audit log." })} />}
            </Field>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/devices/$deviceId" params={{ deviceId }}>Cancel</Link></Button>
            <Button type="submit" variant="danger" loading={form.formState.isSubmitting}>Revoke Device</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
