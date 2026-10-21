import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useMe } from "@/lib/auth";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Input, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";

export const Route = createFileRoute("/system/email-templates/new")({
  validateSearch: z.object({ edition_id: z.string().optional() }),
  component: NewTemplate,
});

// The real QR is attached to the email (cid:); the preview shows a grey square in its place.
const QR_PLACEHOLDER = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><rect width="240" height="240" fill="#e2e2e2"/><text x="120" y="126" font-family="sans-serif" font-size="16" text-anchor="middle" fill="#525252">QR code</text></svg>');

function previewHtml(html: string): string {
  return html.replace(/src=(["'])cid:[^"']*\1/g, `src="${QR_PLACEHOLDER}"`);
}

const VARIABLES = ["first_name", "registration_code", "edition_name", "edition_code", "start_date", "end_date", "city", "qr_cid"];

function NewTemplate() {
  const { edition_id } = Route.useSearch();
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const current = useQuery({
    queryKey: ["email-templates", edition_id ?? "system"],
    queryFn: () => call(api.GET("/api/v1/email-templates", { params: { query: { edition_id, template_key: "QR_CONFIRMATION" } } })),
  });
  const system = useQuery({
    queryKey: ["email-templates", "system"],
    enabled: Boolean(edition_id),
    queryFn: () => call(api.GET("/api/v1/email-templates", { params: { query: { template_key: "QR_CONFIRMATION" } } })),
  });
  const form = useForm<{ subject: string; body_text: string; body_html: string }>({ defaultValues: { subject: "", body_text: "", body_html: "" } });
  const base = current.data?.[0] ?? system.data?.[0];
  useEffect(() => {
    // Start from the version in use, so editing is a change, not a rewrite.
    if (base && !form.formState.isDirty) form.reset({ subject: base.subject, body_text: base.body_text, body_html: base.body_html });
  }, [base, form]);
  const editionLabel = edition_id ? (me.editions.find((e) => e.id === edition_id)?.code ?? "edition") : "system default";

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const t = await call(api.POST("/api/v1/email-templates", { body: { edition_id: edition_id ?? null, template_key: "QR_CONFIRMATION", ...v } }));
      void queryClient.invalidateQueries({ queryKey: ["email-templates"] });
      notifySuccess(`Version ${t.version} saved`, "New QR emails use it from now on.");
      await navigate({ to: "/system/email-templates", search: { edition_id } });
    } catch (e) {
      handleFormError(e, form.setError, ["subject", "body_text", "body_html"]);
    }
  });

  return (
    <Page>
      <PageHead title="New Template Version" meta={`QR confirmation email for the ${editionLabel}.`} back={{ to: "/system/email-templates", label: "Email Templates" }} />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Panel>
          <form onSubmit={onSubmit} noValidate>
            <Section title="Content">
              <div className="flex flex-col gap-4">
                <Field label="Subject" required error={form.formState.errors.subject?.message}>{(p) => <Input {...p} {...form.register("subject", { required: "Enter a subject." })} />}</Field>
                <Field label="Text version" required help="Shown by mail apps that do not display HTML." error={form.formState.errors.body_text?.message}>{(p) => <Textarea {...p} className="min-h-40 font-mono text-[12px]" {...form.register("body_text", { required: "Enter the text version." })} />}</Field>
                <Field label="HTML version" required help={'Must contain <img src="cid:{{ qr_cid }}"> for the QR code. Values are escaped automatically.'} error={form.formState.errors.body_html?.message}>{(p) => <Textarea {...p} className="min-h-60 font-mono text-[12px]" {...form.register("body_html", { required: "Enter the HTML version." })} />}</Field>
              </div>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/system/email-templates" search={{ edition_id }}>Cancel</Link></Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save New Version</Button>
            </FormActions>
          </form>
        </Panel>
        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader title="Variables" />
            <ul className="flex flex-wrap gap-2 p-5">
              {VARIABLES.map((v) => <li key={v}><code className="rounded-[6px] bg-input px-2 py-1 text-[12px]">{`{{ ${v} }}`}</code></li>)}
            </ul>
            <p className="px-5 pb-5 text-[12px] text-label">Unknown variables or template errors are rejected when you save.</p>
          </Panel>
          <Panel>
            <PanelHeader title="HTML preview (variables not filled in)" />
            {/* Sandboxed: no scripts, no same-origin access. */}
            <iframe title="HTML preview" sandbox="" srcDoc={previewHtml(form.watch("body_html"))} className="h-80 w-full rounded-b-[12px] bg-white" />
          </Panel>
        </div>
      </div>
    </Page>
  );
}
