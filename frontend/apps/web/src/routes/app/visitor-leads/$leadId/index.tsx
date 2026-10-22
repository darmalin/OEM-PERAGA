import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useBlocker, useNavigate } from "@tanstack/react-router";
import { CalendarPlus, PhoneCall, Ticket, UserPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { PERSON_FIELDS, personPayload, PersonFields, type PersonValues } from "@/features/leads/person-form";
import { type Lead, leadQuery } from "@/features/leads/queries";
import { can, useMe } from "@/lib/auth";
import { useEditionById } from "@/lib/edition";
import { isFinal } from "@/lib/transitions";
import { handleFormError } from "@/lib/forms";
import { formatDateTime, fromLocalInput, relative, toLocalInput } from "@/lib/format";
import { label, options } from "@/lib/labels";
import { notifyError, notifySuccess } from "@/lib/notify";
import { ActivityTimeline } from "@/ui/activity";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";
import { Indicator } from "@/ui/indicator";
import { ArrayBody } from "@/ui/list";
import { Facts, FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";
import { TabList, TabPanel, Tabs } from "@/ui/tabs";

const TABS = ["person", "verification", "calls", "registration", "activity"] as const;

export const Route = createFileRoute("/app/visitor-leads/$leadId/")({
  validateSearch: z.object({ tab: z.enum(TABS).default("person") }),
  component: LeadDetail,
});

function LeadDetail() {
  const { leadId } = Route.useParams();
  const { tab } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const me = useMe();
  const lead = useQuery(leadQuery(leadId));
  const edition = useEditionById(lead.data?.edition_id);
  const tz = edition?.timezone;

  if (lead.isPending) {
    return (
      <Page>
        <PageHead title="Loading visitor lead" back={{ to: "/app/visitor-leads", label: "Visitor Leads" }} />
        <Panel><FormSkeleton /></Panel>
      </Page>
    );
  }
  if (lead.isError) {
    return (
      <Page>
        <PageHead title="Visitor lead" back={{ to: "/app/visitor-leads", label: "Visitor Leads" }} />
        <Panel><ErrorState error={lead.error} onRetry={() => void lead.refetch()} /></Panel>
      </Page>
    );
  }
  const l = lead.data;
  const registered = l.registration_status === "REGISTERED";

  return (
    <Page>
      <PageHead
        back={{ to: "/app/visitor-leads", label: "Visitor Leads" }}
        title={l.first_name}
        meta={
          <span className="tabular">
            {l.registration_code} · {label("source", l.source)} · created {relative(l.created_at)}
          </span>
        }
        indicators={
          <>
            <Indicator value={l.telemarketing_status} group="telemarketing_status" />
            <Indicator value={l.registration_status} group="registration_status" />
            {l.qr_status !== "NONE" ? <Indicator value={l.qr_status} group="qr_status" /> : null}
          </>
        }
        actions={
          <>
            {can(me, "telemarketing.followup") ? (
              <Button asChild>
                <Link to="/app/visitor-leads/$leadId/followup" params={{ leadId }}><CalendarPlus aria-hidden />Add Follow-up</Link>
              </Button>
            ) : null}
            {!registered && can(me, "registration.create") ? (
              <Button asChild>
                <Link to="/app/visitor-leads/$leadId/register" params={{ leadId }}><Ticket aria-hidden />Register Visitor</Link>
              </Button>
            ) : null}
            {can(me, "telemarketing.call") && !isFinal(l.telemarketing_status) ? (
              <Button asChild variant="primary">
                <Link to="/app/visitor-leads/$leadId/log-call" params={{ leadId }}><PhoneCall aria-hidden />Log Call</Link>
              </Button>
            ) : null}
          </>
        }
      />
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_300px]">
        <Panel className="min-w-0">
          <Tabs value={tab} onValueChange={(v) => void navigate({ search: { tab: v as (typeof TABS)[number] }, replace: true })}>
            <TabList
              tabs={[
                { value: "person", label: "Person" },
                { value: "verification", label: "Verification" },
                { value: "calls", label: `Calls (${l.call_attempts})` },
                { value: "registration", label: "Registration" },
                { value: "activity", label: "Activity" },
              ]}
            />
            <TabPanel value="person"><PersonTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="verification"><VerificationTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="calls"><CallsTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="registration"><RegistrationTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="activity"><ActivityTab leadId={l.id} timezone={tz} /></TabPanel>
          </Tabs>
        </Panel>
        <aside className="flex flex-col gap-6">
          <Panel>
            <PanelHeader
              title="Assigned To"
              actions={
                can(me, "visitor.assign") ? (
                  <Button asChild size="sm" variant="ghost">
                    <Link to="/app/visitor-leads/assign" state={{ leadIds: [l.id], editionId: l.edition_id }}><UserPlus aria-hidden />{l.lead_owner_id ? "Reassign" : "Assign"}</Link>
                  </Button>
                ) : null
              }
            />
            <div className="p-5 text-[14px]">
              {l.lead_owner_name ?? <span className="text-label">Unassigned</span>}
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Follow-up and calls" />
            <div className="p-5">
              <Facts
                items={[
                  ["Next follow-up", l.next_followup_at ? formatDateTime(l.next_followup_at, tz) : null],
                  ["Last call", l.last_call_at ? formatDateTime(l.last_call_at, tz) : null],
                  ["Attempts", String(l.call_attempts)],
                ]}
              />
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Record" />
            <div className="p-5">
              <Facts
                items={[
                  ["Source", label("source", l.source)],
                  ["External ID", l.external_id ? `${l.external_source ?? ""} ${l.external_id}` : null],
                  ["Created", formatDateTime(l.created_at, tz)],
                  ["Modified", formatDateTime(l.updated_at, tz)],
                ]}
              />
            </div>
          </Panel>
        </aside>
      </div>
    </Page>
  );
}

function toValues(l: Lead, tz?: string): PersonValues {
  return {
    lead_date: tz ? toLocalInput(l.lead_date, tz) : l.lead_date.slice(0, 16),
    first_name: l.first_name,
    email: l.email ?? "",
    phone: l.phone ?? "",
    gender: l.gender ?? "",
    company_name: l.company_name ?? "",
    job_title: l.job_title ?? "",
    country: l.country ?? "",
    city: l.city ?? "",
    website: l.website ?? "",
    business_type: l.business_type ?? "",
    branch: l.branch ?? "",
    product_categories: l.product_categories,
    comment: l.comment ?? "",
    custom_fields: l.custom_fields,
  };
}

function PersonTab({ lead, timezone }: { lead: Lead; timezone?: string }) {
  const me = useMe();
  const edition = useEditionById(lead.edition_id);
  const queryClient = useQueryClient();
  const editable = can(me, "visitor.update");
  const form = useForm<PersonValues>({ defaultValues: toValues(lead, timezone) });
  const [conflict, setConflict] = useState(false);
  const { isDirty, dirtyFields, isSubmitting } = form.formState;

  useEffect(() => {
    if (!form.formState.isDirty) form.reset(toValues(lead, timezone));
  }, [lead, timezone, form]);

  useBlocker({
    shouldBlockFn: () => isDirty && !window.confirm("You have unsaved changes. Leave this page?"),
    disabled: !isDirty,
  });

  const save = form.handleSubmit(async (values) => {
    setConflict(false);
    try {
      const body: Record<string, unknown> = { ...personPayload(values, dirtyFields as Record<string, unknown>), version: lead.version };
      if (body.lead_date && timezone) body.lead_date = fromLocalInput(values.lead_date, timezone);
      const updated = await call(
        api.PATCH("/api/v1/visitor-leads/{lead_id}", { params: { path: { lead_id: lead.id } }, body: body as never }),
      );
      queryClient.setQueryData(["lead", lead.id], updated);
      form.reset(toValues(updated, timezone));
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      notifySuccess("Saved", updated.registration_code);
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") setConflict(true);
      handleFormError(e, form.setError, PERSON_FIELDS);
    }
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (editable) void save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save, editable]);

  return (
    <form onSubmit={save} noValidate>
      {conflict ? (
        <div role="alert" className="mx-5 mt-5 flex flex-wrap items-center justify-between gap-3 rounded-[8px] bg-[var(--amber-bg)] px-4 py-3 text-[13px] text-[var(--amber-fg)]">
          <span>This lead was changed by someone else. Your edits are still in the form; copy what you need, then reload.</span>
          <Button size="sm" type="button" onClick={() => { setConflict(false); form.reset(toValues(lead, timezone)); void queryClient.invalidateQueries({ queryKey: ["lead", lead.id] }); }}>
            Reload
          </Button>
        </div>
      ) : null}
      <PersonFields
        editionId={lead.edition_id}
        register={form.register}
        control={form.control}
        errors={form.formState.errors}
        readOnly={!editable}
        exhibitionType={
          <Field label="Exhibition Type" help="The edition of this lead; set when it was created.">
            {(p) => <Input {...p} value={edition ? `${edition.code} · ${edition.name}` : lead.edition_id} readOnly className="text-muted" />}
          </Field>
        }
        systemCells={
          <>
            <Field label="Registration ID" help="Issued by the system.">
              {(p) => <Input {...p} value={lead.registration_code} readOnly className="text-muted tabular" />}
            </Field>
            <Field label="Status" help="Follows the call history.">
              {(p) => <Input {...p} value={label("telemarketing_status", lead.telemarketing_status)} readOnly className="text-muted" />}
            </Field>
          </>
        }
      />
      {editable ? (
        <FormActions>
          {isDirty ? <Indicator value="DRAFT" text="Not Saved" className="mr-auto" /> : null}
          <Button type="button" variant="ghost" disabled={!isDirty} onClick={() => form.reset(toValues(lead, timezone))}>Discard Changes</Button>
          <Button type="submit" variant="primary" disabled={!isDirty} loading={isSubmitting}>Save <kbd className="text-[11px] opacity-70">Ctrl S</kbd></Button>
        </FormActions>
      ) : null}
    </form>
  );
}

interface VerificationValues {
  validity: "VALID" | "INVALID" | "UNDECIDED";
  attend: string;
  buyer_type: string;
  b2b_matching: boolean;
}

function VerificationTab({ lead, timezone }: { lead: Lead; timezone?: string }) {
  const me = useMe();
  const queryClient = useQueryClient();
  const editable = can(me, "visitor.verify");
  const initial = (l: Lead): VerificationValues => ({
    validity: l.is_valid_lead ? "VALID" : l.is_invalid ? "INVALID" : "UNDECIDED",
    attend: l.attend ?? "",
    buyer_type: l.buyer_type ?? "",
    b2b_matching: l.b2b_matching,
  });
  const form = useForm<VerificationValues>({ defaultValues: initial(lead) });
  const history = useQuery({
    queryKey: ["verifications", lead.id],
    queryFn: () => call(api.GET("/api/v1/visitor-leads/{lead_id}/verifications", { params: { path: { lead_id: lead.id } } })),
  });

  const save = form.handleSubmit(async (v) => {
    try {
      const updated = await call(
        api.PATCH("/api/v1/visitor-leads/{lead_id}/verification", {
          params: { path: { lead_id: lead.id } },
          body: {
            version: lead.version,
            is_valid_lead: v.validity === "VALID",
            is_invalid: v.validity === "INVALID",
            attend: (v.attend || null) as never,
            buyer_type: (v.buyer_type || null) as never,
            b2b_matching: v.b2b_matching,
          },
        }),
      );
      queryClient.setQueryData(["lead", lead.id], updated);
      form.reset(initial(updated));
      void history.refetch();
      notifySuccess("Verification saved");
    } catch (e) {
      notifyError(e);
    }
  });

  return (
    <form onSubmit={save} noValidate>
      <Section title="Verification">
        <FieldGrid>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 text-[13px] text-label">Lead Quality</legend>
            {(["VALID", "INVALID", "UNDECIDED"] as const).map((v) => (
              <label key={v} className="flex items-center gap-2 text-[14px]">
                <input type="radio" value={v} disabled={!editable} {...form.register("validity")} className="size-4 accent-[var(--primary)]" />
                {label("validity", v)}
              </label>
            ))}
          </fieldset>
          <div className="flex flex-col gap-4">
            <Field label="Attend" help="What the visitor said on the call.">
              {(p) => (
                <Select {...p} disabled={!editable} {...form.register("attend")}>
                  <option value="">Not set</option>
                  {options("attend").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              )}
            </Field>
            <Field label="Type of Buyers">
              {(p) => (
                <Select {...p} disabled={!editable} {...form.register("buyer_type")}>
                  <option value="">Not set</option>
                  {options("buyer_type").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              )}
            </Field>
          </div>
          <div className="flex flex-col gap-4">
            <label className="flex h-8 items-center gap-2 text-[14px]">
              <Checkbox
                checked={form.watch("b2b_matching")}
                disabled={!editable}
                onCheckedChange={(v) => form.setValue("b2b_matching", v === true, { shouldDirty: true })}
              />
              B2B Matching
            </label>
            <Field label="Updated At">
              {(p) => <Input {...p} readOnly value={lead.verification_updated_at ? formatDateTime(lead.verification_updated_at, timezone) : "Not verified yet"} className="text-muted tabular" />}
            </Field>
          </div>
        </FieldGrid>
      </Section>
      {editable ? (
        <FormActions>
          <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Verification</Button>
        </FormActions>
      ) : null}
      <Section title="Verification history" defaultOpen={false}>
        <ArrayBody query={history} empty={<p className="text-[13px] text-muted">No verification saved yet.</p>}>
          {(rows) => (
            <ul className="flex flex-col divide-y divide-line text-[13px]">
              {rows.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-2 py-2">
                  <span className="w-40 text-label tabular">{formatDateTime(r.created_at, timezone)}</span>
                  <Indicator value={r.is_valid_lead ? "VALID" : r.is_invalid ? "INVALID" : "UNDECIDED"} group="validity" />
                  {r.attend ? <Indicator value={r.attend} group="attend" /> : null}
                  {r.buyer_type ? <span className="text-muted">{label("buyer_type", r.buyer_type)}</span> : null}
                  {r.b2b_matching ? <span className="text-muted">B2B Matching</span> : null}
                </li>
              ))}
            </ul>
          )}
        </ArrayBody>
      </Section>
    </form>
  );
}

function CallsTab({ lead, timezone }: { lead: Lead; timezone?: string }) {
  const me = useMe();
  const calls = useQuery({
    queryKey: ["calls", lead.id],
    queryFn: () => call(api.GET("/api/v1/visitor-leads/{lead_id}/calls", { params: { path: { lead_id: lead.id } } })),
  });
  return (
    <div className="p-5">
      <ArrayBody
        query={calls}
        empty={
          <EmptyState
            title="No calls logged yet."
            action={can(me, "telemarketing.call") && !isFinal(lead.telemarketing_status) ? <Button asChild variant="primary"><Link to="/app/visitor-leads/$leadId/log-call" params={{ leadId: lead.id }}>Log Call</Link></Button> : undefined}
          />
        }
      >
        {(rows) => (
          <ol className="flex flex-col divide-y divide-line">
            {rows.map((c) => (
              <li key={c.id} className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 py-3 text-[13px]">
                <span className="font-medium tabular">#{c.attempt_number}</span>
                <span className="flex flex-wrap items-center gap-2">
                  <Indicator value={c.call_result === "ANSWER" ? "ANSWER" : "NO_ANSWER"} text={label("call_result", c.call_result)} />
                  <span className="text-label tabular">{formatDateTime(c.called_at, timezone)}</span>
                  {c.duration_seconds ? <span className="text-label tabular">{Math.round(c.duration_seconds / 60)} min</span> : null}
                </span>
                {c.notes ? <p className="col-start-2 whitespace-pre-wrap text-muted">{c.notes}</p> : null}
              </li>
            ))}
          </ol>
        )}
      </ArrayBody>
    </div>
  );
}

function RegistrationTab({ lead, timezone }: { lead: Lead; timezone?: string }) {
  const me = useMe();
  const regs = useQuery({
    queryKey: ["registrations", "lead", lead.id],
    enabled: can(me, "registration.read"),
    queryFn: () =>
      call(api.GET("/api/v1/visitor-registrations", { params: { query: { edition_id: lead.edition_id, visitor_lead_id: lead.id } } })),
  });
  if (!can(me, "registration.read")) return <EmptyState title="You can't view registrations." />;
  if (regs.isPending) return <FormSkeleton />;
  if (regs.isError) return <ErrorState error={regs.error} onRetry={() => void regs.refetch()} />;
  const reg = regs.data.items[0];
  if (!reg) {
    return (
      <EmptyState
        title="Not registered. Registering issues a QR code and emails it to the visitor."
        action={can(me, "registration.create") ? <Button asChild variant="primary"><Link to="/app/visitor-leads/$leadId/register" params={{ leadId: lead.id }}>Register Visitor</Link></Button> : undefined}
      />
    );
  }
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 p-5">
      <Facts
        items={[
          ["Registered", formatDateTime(reg.registered_at, timezone)],
          ["Channel", label("channel", reg.channel)],
          ["QR", <Indicator key="qr" value={reg.qr_status} group="qr_status" />],
          ["QR email", reg.email_status ? <Indicator key="em" value={reg.email_status} group="email_status" /> : "No email sent"],
        ]}
      />
      <Button asChild><Link to="/app/registrations/$registrationId" params={{ registrationId: reg.id }}>Open Registration</Link></Button>
    </div>
  );
}

function ActivityTab({ leadId, timezone }: { leadId: string; timezone?: string }) {
  const q = useQuery({
    queryKey: ["activity", leadId],
    queryFn: () => call(api.GET("/api/v1/visitor-leads/{lead_id}/activity", { params: { path: { lead_id: leadId } } })),
  });
  return (
    <div className="p-5">
      <ArrayBody query={q} empty={<p className="text-[13px] text-muted">No activity yet.</p>}>
        {(rows) => <ActivityTimeline entries={rows} timezone={timezone} />}
      </ArrayBody>
    </div>
  );
}
