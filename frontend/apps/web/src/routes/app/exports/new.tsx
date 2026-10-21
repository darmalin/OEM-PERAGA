import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { can, useMe } from "@/lib/auth";
import { useEdition } from "@/lib/edition";
import { notifyError, notifySuccess } from "@/lib/notify";
import { options } from "@/lib/labels";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/exports/new")({ component: NewExport });

const REPORTS = ["LEADS", "TELEMARKETING", "VERIFICATION", "REGISTRATION", "AGENTS", "ATTENDANCE", "GATES", "IMPORTS", "EMAILS"] as const;

interface Values {
  kind: "VISITORS" | "REPORT";
  telemarketing_status: string;
  registration_status: string;
  source: string;
  report: (typeof REPORTS)[number];
  date_from: string;
  date_to: string;
}

function NewExport() {
  const me = useMe();
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<Values>({
    defaultValues: { kind: can(me, "visitor.export") ? "VISITORS" : "REPORT", telemarketing_status: "", registration_status: "", source: "", report: "LEADS", date_from: "", date_to: "" },
  });
  if (!edition) return <Page><NoEdition /></Page>;
  const kind = form.watch("kind");

  const onSubmit = form.handleSubmit(async (v) => {
    try {
      if (v.kind === "VISITORS") {
        await call(api.POST("/api/v1/exports/visitors", {
          body: {
            edition_id: edition.id,
            telemarketing_status: v.telemarketing_status ? [v.telemarketing_status as "NEW"] : undefined,
            registration_status: (v.registration_status || undefined) as "REGISTERED" | undefined,
            source: (v.source || undefined) as "MANUAL" | undefined,
          },
        }));
      } else {
        await call(api.POST("/api/v1/exports/reports", {
          body: { edition_id: edition.id, report: v.report, date_from: v.date_from || undefined, date_to: v.date_to || undefined },
        }));
      }
      void queryClient.invalidateQueries({ queryKey: ["exports"] });
      notifySuccess("Export started", "It appears in the list when it is ready.");
      await navigate({ to: "/app/exports" });
    } catch (e) {
      notifyError(e);
    }
  });

  return (
    <Page className="max-w-[960px]">
      <PageHead title="New Export" meta={`From ${edition.code}. You get what you are allowed to see, nothing more.`} back={{ to: "/app/exports", label: "Exports" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="What to export">
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Export type">
              {[
                { v: "VISITORS" as const, t: "Visitor leads", d: "One row per lead, with custom fields.", ok: can(me, "visitor.export") },
                { v: "REPORT" as const, t: "Report", d: "The numbers of one report.", ok: can(me, "report.export") },
              ].filter((o) => o.ok).map((o) => (
                <label key={o.v} className="flex min-w-[240px] flex-1 cursor-pointer flex-col gap-0.5 rounded-[10px] border border-line px-4 py-3 has-[:checked]:border-ink has-[:checked]:bg-subtle has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus">
                  <input type="radio" value={o.v} className="sr-only" {...form.register("kind")} />
                  <span className="text-[14px] font-medium">{o.t}</span>
                  <span className="text-[13px] text-label">{o.d}</span>
                </label>
              ))}
            </div>
          </Section>
          <Section title={kind === "VISITORS" ? "Filters" : "Report"}>
            {kind === "VISITORS" ? (
              <FieldGrid>
                {(["telemarketing_status", "registration_status", "source"] as const).map((f) => (
                  <Field key={f} label={f === "telemarketing_status" ? "Status" : f === "registration_status" ? "Registration" : "Source"}>
                    {(p) => (
                      <Select {...p} {...form.register(f)}>
                        <option value="">All</option>
                        {options(f).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </Select>
                    )}
                  </Field>
                ))}
              </FieldGrid>
            ) : (
              <FieldGrid>
                <Field label="Report" required>
                  {(p) => (
                    <Select {...p} {...form.register("report")}>
                      {REPORTS.map((r) => <option key={r} value={r}>{r.charAt(0) + r.slice(1).toLowerCase()}</option>)}
                    </Select>
                  )}
                </Field>
                <Field label="From" help="Event-local date.">{(p) => <Input {...p} type="date" {...form.register("date_from")} />}</Field>
                <Field label="To">{(p) => <Input {...p} type="date" {...form.register("date_to")} />}</Field>
              </FieldGrid>
            )}
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/exports">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Start Export</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
