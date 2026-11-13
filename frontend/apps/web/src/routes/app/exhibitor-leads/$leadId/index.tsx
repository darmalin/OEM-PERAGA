import { api, ApiError, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useBlocker, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ContractTab } from "@/features/exhibitors/contract-tab";
import { ExhibitorLeadFields, LEAD_FIELDS, leadBody, type ExhibitorLeadValues } from "@/features/exhibitors/lead-form";
import { PaymentsTab } from "@/features/exhibitors/payments-tab";
import { LeadOrdersTab } from "@/features/order-forms/lead-orders-tab";
import { PortalAccountPanel } from "@/features/exhibitors/portal-account-panel";
import { contractQuery, type ExhibitorLead, exhibitorLeadQuery, leadOwnersQuery, STAGE_MOVES } from "@/features/exhibitors/queries";
import { can, useMe } from "@/lib/auth";
import { useEditionById } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { formatDateTime, formatMoney, relative } from "@/lib/format";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { ActivityTimeline } from "@/ui/activity";
import { Button } from "@/ui/button";
import { Field } from "@/ui/field";
import { Indicator } from "@/ui/indicator";
import { Input } from "@/ui/input";
import { ArrayBody } from "@/ui/list";
import { Facts, FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";
import { TabList, TabPanel, Tabs } from "@/ui/tabs";

const TABS = ["details", "contract", "payments", "orders", "activity"] as const;

export const Route = createFileRoute("/app/exhibitor-leads/$leadId/")({
  validateSearch: z.object({ tab: z.enum(TABS).default("details") }),
  component: ExhibitorLeadDetail,
});

const BACK = { to: "/app/exhibitor-leads", label: "Exhibitor Leads" };

function ExhibitorLeadDetail() {
  const { leadId } = Route.useParams();
  const { tab } = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const me = useMe();
  const lead = useQuery(exhibitorLeadQuery(leadId));
  const edition = useEditionById(lead.data?.edition_id);
  // A signed contract freezes the booth (exhibitors/service.py assign_booth).
  const contract = useQuery({ ...contractQuery(leadId), enabled: lead.data?.stage === "EXHIBITOR" });
  const tz = edition?.timezone;

  if (lead.isPending) {
    return <Page><PageHead title="Loading exhibitor lead" back={BACK} /><Panel><FormSkeleton /></Panel></Page>;
  }
  if (lead.isError) {
    return <Page><PageHead title="Exhibitor lead" back={BACK} /><Panel><ErrorState error={lead.error} onRetry={() => void lead.refetch()} /></Panel></Page>;
  }
  const l = lead.data;
  const exhibitor = l.stage === "EXHIBITOR";

  return (
    <Page>
      <PageHead
        back={BACK}
        title={l.company_name}
        meta={`${l.contact_name} · ${edition?.code ?? ""} · created ${relative(l.created_at)}`}
        indicators={<Indicator value={l.stage} group="sales_stage" />}
        actions={
          l.stage === "OPPORTUNITY" && l.booth_id && can(me, "exhibitor.invite") ? (
            <Button asChild variant="primary">
              <Link to="/app/exhibitor-leads/$leadId/convert" params={{ leadId }}>Convert to Exhibitor</Link>
            </Button>
          ) : null
        }
      />
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_300px]">
        <Panel className="min-w-0">
          <Tabs value={tab} onValueChange={(v) => void navigate({ search: { tab: v as (typeof TABS)[number] }, replace: true })}>
            <TabList
              tabs={[
                { value: "details", label: "Details" },
                { value: "contract", label: "Contract" },
                { value: "payments", label: "Payments" },
                { value: "orders", label: "Orders" },
                { value: "activity", label: "Activity" },
              ]}
            />
            <TabPanel value="details"><DetailsTab lead={l} /></TabPanel>
            <TabPanel value="contract"><ContractTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="payments"><PaymentsTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="orders"><LeadOrdersTab lead={l} timezone={tz} /></TabPanel>
            <TabPanel value="activity"><ActivityTab leadId={l.id} timezone={tz} /></TabPanel>
          </Tabs>
        </Panel>
        <aside className="flex flex-col gap-6">
          <StagePanel lead={l} timezone={tz} />
          <Panel>
            <PanelHeader
              title="Booth"
              actions={
                (l.stage === "OPPORTUNITY" || (exhibitor && contract.data?.status === "DRAFT")) && can(me, "exhibitor_lead.update") ? (
                  <Button asChild size="sm" variant="ghost">
                    <Link to="/app/exhibitor-leads/$leadId/booth" params={{ leadId }}>{l.booth_id ? "Change Booth or Price" : "Choose Booth"}</Link>
                  </Button>
                ) : null
              }
            />
            <div className="p-5 text-[14px]">
              {l.booth_code ? (
                <>
                  <p><span className="tabular font-medium">{l.booth_code}</span> <span className="text-[12px] text-label">since {formatDateTime(l.booth_assigned_at, tz)}</span></p>
                  <p className="mt-1 tabular">{formatMoney(l.booth_price, l.booth_currency ?? "")}</p>
                  {l.booth_list_price && l.booth_price !== l.booth_list_price ? (
                    <p className="text-[12px] text-label tabular">List price {formatMoney(l.booth_list_price, l.booth_currency ?? "")}</p>
                  ) : null}
                </>
              ) : (
                <p className="text-[13px] text-label">{l.stage === "LEAD" || l.stage === "LOST" ? "Mark the lead as Opportunity to hold a booth." : "No booth yet."}</p>
              )}
            </div>
          </Panel>
          {exhibitor ? <PortalAccountPanel lead={l} timezone={tz} /> : null}
          <OwnerPanel lead={l} />
          <Panel>
            <PanelHeader title="Record" />
            <div className="p-5">
              <Facts
                items={[
                  ...(l.converted_at ? ([["Converted", formatDateTime(l.converted_at, tz)]] as [string, string][]) : []),
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

function OwnerPanel({ lead }: { lead: ExhibitorLead }) {
  const me = useMe();
  const owners = useQuery(leadOwnersQuery(lead.edition_id));
  const assign = can(me, "exhibitor_lead.update") && owners.data?.can_assign;
  return (
    <Panel>
      <PanelHeader
        title="Lead Owner"
        actions={
          assign ? (
            <Button asChild size="sm" variant="ghost">
              <Link to="/app/exhibitor-leads/$leadId/owner" params={{ leadId: lead.id }}>{lead.lead_owner_id ? "Reassign" : "Assign"}</Link>
            </Button>
          ) : null
        }
      />
      <div className="p-5 text-[14px]">{lead.lead_owner_name ?? <span className="text-label">Unassigned</span>}</div>
    </Panel>
  );
}

function StagePanel({ lead, timezone }: { lead: ExhibitorLead; timezone?: string }) {
  const me = useMe();
  const moves = can(me, "exhibitor_lead.update") ? (STAGE_MOVES[lead.stage] ?? []) : [];
  return (
    <Panel>
      <PanelHeader title="Stage" />
      <div className="flex flex-col gap-3 p-5 text-[13px]">
        <Facts
          items={[
            ["Stage", <Indicator key="s" value={lead.stage} group="sales_stage" />],
            ...(lead.qualified_at ? ([["Opportunity", formatDateTime(lead.qualified_at, timezone)]] as [string, string][]) : []),
            ...(lead.stage === "LOST" ? ([["Lost Reason", lead.lost_reason]] as [string, string | null][]) : []),
          ]}
        />
        {moves.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {moves.map((to) => (
              <Button key={to} asChild size="sm" variant={to === "LOST" ? "danger" : "secondary"}>
                <Link to="/app/exhibitor-leads/$leadId/stage" params={{ leadId: lead.id }} search={{ to }}>
                  {to === "LEAD" && lead.stage === "LOST" ? "Reopen" : to === "LEAD" ? "Back to Lead" : `Mark ${label("sales_stage", to)}`}
                </Link>
              </Button>
            ))}
          </div>
        ) : null}
      </div>
    </Panel>
  );
}

const toValues = (l: ExhibitorLead): ExhibitorLeadValues => ({
  edition_id: l.edition_id,
  lead_owner_id: l.lead_owner_id ?? "",
  company_name: l.company_name,
  contact_name: l.contact_name,
  email: l.email,
  phone: l.phone ?? "",
  product_categories: l.product_categories ?? "",
  booth_preference: l.booth_preference ?? "",
  budget_estimate: l.budget_estimate ?? "",
  notes: l.notes ?? "",
});

function DetailsTab({ lead }: { lead: ExhibitorLead }) {
  const me = useMe();
  const edition = useEditionById(lead.edition_id);
  const queryClient = useQueryClient();
  const editable = can(me, "exhibitor_lead.update");
  const form = useForm<ExhibitorLeadValues>({ defaultValues: toValues(lead) });
  const [conflict, setConflict] = useState(false);
  const { isDirty, isSubmitting } = form.formState;

  useEffect(() => {
    if (!form.formState.isDirty) form.reset(toValues(lead));
  }, [lead, form]);

  useBlocker({
    shouldBlockFn: () => isDirty && !window.confirm("You have unsaved changes. Leave this page?"),
    disabled: !isDirty,
  });

  const save = form.handleSubmit(async (v) => {
    setConflict(false);
    try {
      const updated = await call(
        api.PATCH("/api/v1/exhibitor-leads/{lead_id}", { params: { path: { lead_id: lead.id } }, body: { ...leadBody(v), version: lead.version } }),
      );
      queryClient.setQueryData(["exhibitor-lead", lead.id], updated);
      form.reset(toValues(updated));
      void queryClient.invalidateQueries({ queryKey: ["exhibitor-leads"] });
      notifySuccess("Saved", updated.company_name);
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") setConflict(true);
      handleFormError(e, form.setError, LEAD_FIELDS);
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
          <Button size="sm" type="button" onClick={() => { setConflict(false); form.reset(toValues(lead)); void queryClient.invalidateQueries({ queryKey: ["exhibitor-lead", lead.id] }); }}>
            Reload
          </Button>
        </div>
      ) : null}
      <ExhibitorLeadFields
        register={form.register}
        errors={form.formState.errors}
        readOnly={!editable}
        edition={
          <Field label="Exhibition Type" help="Set when the lead was created.">
            {(p) => <Input {...p} value={edition ? `${edition.code} · ${edition.name}` : lead.edition_id} readOnly className="text-muted" />}
          </Field>
        }
      />
      {editable ? (
        <FormActions>
          {isDirty ? <Indicator value="DRAFT" text="Not Saved" className="mr-auto" /> : null}
          <Button type="button" variant="ghost" disabled={!isDirty} onClick={() => form.reset(toValues(lead))}>Discard Changes</Button>
          <Button type="submit" variant="primary" disabled={!isDirty} loading={isSubmitting}>Save <kbd className="text-[11px] opacity-70">Ctrl S</kbd></Button>
        </FormActions>
      ) : null}
    </form>
  );
}

function ActivityTab({ leadId, timezone }: { leadId: string; timezone?: string }) {
  const q = useQuery({
    queryKey: ["exhibitor-lead", leadId, "activity"],
    queryFn: () => call(api.GET("/api/v1/exhibitor-leads/{lead_id}/activity", { params: { path: { lead_id: leadId } } })),
  });
  return (
    <div className="p-5">
      <ArrayBody query={q} empty={<p className="text-[13px] text-muted">No activity yet.</p>}>
        {(rows) => <ActivityTimeline entries={rows} timezone={timezone} />}
      </ArrayBody>
    </div>
  );
}
