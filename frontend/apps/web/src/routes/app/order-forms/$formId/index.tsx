import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FileUp, ImageIcon, Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  DETAILS_TYPES,
  formParts,
  orderFormItemsQuery,
  orderFormQuery,
  PURPOSES,
  type OrderForm,
  type OrderFormItem,
} from "@/features/order-forms/queries";
import { OptionsSection } from "@/features/order-forms/answers";
import { can, useMe } from "@/lib/auth";
import { useEditionById } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { formatDate, formatMoney } from "@/lib/format";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Indicator } from "@/ui/indicator";
import { Facts, FormActions, Page, PageHead, Panel, PanelHeader } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton, TableSkeleton } from "@/ui/states";
import { type Column, ListTable } from "@/ui/table";
import { TabList, TabPanel, Tabs } from "@/ui/tabs";

import { FORM_FIELDS, formBody, formValues, OrderFormFields, type FormValues } from "../-form";

const TABS = ["catalog", "settings"] as const;

export const Route = createFileRoute("/app/order-forms/$formId/")({
  validateSearch: z.object({ tab: z.enum(TABS).optional() }),
  component: OrderFormDetail,
});

const BACK = { to: "/app/order-forms", label: "Order Forms" };

function OrderFormDetail() {
  const { formId } = Route.useParams();
  const search = Route.useSearch();
  const navigate = useNavigate({ from: Route.fullPath });
  const me = useMe();
  const q = useQuery(orderFormQuery(formId));
  const edition = useEditionById(q.data?.edition_id);
  if (q.isPending) return <Page><PageHead title="Loading order form" back={BACK} /><Panel><FormSkeleton /></Panel></Page>;
  if (q.isError) return <Page><PageHead title="Order form" back={BACK} /><Panel><ErrorState error={q.error} onRetry={() => void q.refetch()} /></Panel></Page>;
  const f = q.data;
  const manage = can(me, "order_form.manage");
  // A catalog form opens on its catalog; a questions-only form on its settings.
  const tab = search.tab ?? (f.has_catalog ? "catalog" : "settings");
  return (
    <Page>
      <PageHead
        back={BACK}
        title={`${f.code} · ${f.title}`}
        meta={`${edition?.code ?? ""} · ${formParts(f)}`}
        indicators={f.is_published ? <Indicator value="ACTIVE" text="Published" /> : <Indicator value="DRAFT" text="Not Published" />}
      />
      <Panel>
        <Tabs value={tab} onValueChange={(v) => void navigate({ search: { tab: v as (typeof TABS)[number] }, replace: true })}>
          <TabList tabs={[{ value: "catalog", label: "Catalog" }, { value: "settings", label: "Settings" }]} />
          <TabPanel value="catalog"><Catalog form={f} manage={manage} /></TabPanel>
          <TabPanel value="settings">{manage ? <><Settings form={f} /><OptionsSection form={f} /></> : <SettingsFacts form={f} />}</TabPanel>
        </Tabs>
      </Panel>
    </Page>
  );
}

function Settings({ form: f }: { form: OrderForm }) {
  const queryClient = useQueryClient();
  const form = useForm<FormValues>({ values: formValues(f) });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const saved = await call(api.PATCH("/api/v1/order-forms/{form_id}", { params: { path: { form_id: f.id } }, body: { ...formBody(v), version: f.version } }));
      queryClient.setQueryData(orderFormQuery(f.id).queryKey, saved);
      void queryClient.invalidateQueries({ queryKey: ["order-forms", f.edition_id] });
      notifySuccess(`Form ${saved.code} saved`, saved.is_published ? "Published to the exhibitor portal." : undefined);
    } catch (e) {
      handleFormError(e, form.setError, FORM_FIELDS);
    }
  });
  return (
    <form onSubmit={onSubmit} noValidate>
      <OrderFormFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} isNew={false} />
      <FormActions>
        <Button type="button" variant="ghost" disabled={!form.formState.isDirty} onClick={() => form.reset(formValues(f))}>Discard Changes</Button>
        <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Form</Button>
      </FormActions>
    </form>
  );
}

function SettingsFacts({ form: f }: { form: OrderForm }) {
  return (
    <div className="p-1">
      <Facts
        items={[
          ["Currency", f.currency],
          ["Questions", f.details_type ? DETAILS_TYPES[f.details_type] : "None"],
          ["Attachments", f.attachment_purposes.map((p) => PURPOSES[p]).join(", ") || "None"],
          ["Deadline", formatDate(f.deadline_on)],
          ["Closes On", f.closes_on ? formatDate(f.closes_on) : "Order Expired date of the edition"],
          [f.secondary_deadline_label ?? "Second Deadline", formatDate(f.secondary_deadline_on)],
        ]}
      />
      {f.instructions ? <p className="mt-4 max-w-3xl whitespace-pre-line text-[14px]">{f.instructions}</p> : null}
    </div>
  );
}

function price(value: string | null | undefined, currency: string) {
  return value == null ? <span className="text-label">Regular</span> : <span className="tabular">{formatMoney(value, currency)}</span>;
}

function Catalog({ form: f, manage }: { form: OrderForm; manage: boolean }) {
  const q = useQuery(orderFormItemsQuery(f.id));
  const actions = manage ? (
    <div className="flex flex-wrap gap-2">
      <Button asChild size="sm"><Link to="/app/order-forms/$formId/import" params={{ formId: f.id }}><FileUp aria-hidden />Import from Excel</Link></Button>
      <Button asChild size="sm" variant="primary"><Link to="/app/order-forms/$formId/items/new" params={{ formId: f.id }}><Plus aria-hidden />Add Item</Link></Button>
    </div>
  ) : null;
  const columns: Column<OrderFormItem>[] = [
    { key: "code", header: "Code", cell: (i) => <span className="tabular">{i.code}</span> },
    {
      key: "name",
      header: "Item",
      cell: (i) => (
        <span className="flex items-center gap-2">
          {i.has_image ? <ImageIcon aria-label="Has a picture" className="size-4 shrink-0 text-label" /> : null}
          <span>{i.name}</span>
          {i.size ? <span className="text-label">{i.size}</span> : null}
          {i.allowances?.length ? <span className="text-[12px] text-label">· free by booth size</span> : null}
        </span>
      ),
    },
    { key: "section", header: "Section", hideBelow: "lg", cell: (i) => i.section ?? "" },
    { key: "regular", header: "Regular", className: "text-right", cell: (i) => <span className="tabular">{formatMoney(i.price_regular, f.currency)}</span> },
    { key: "surcharge", header: "Surcharge", className: "text-right", hideBelow: "md", cell: (i) => price(i.price_surcharge, f.currency) },
    { key: "onsite", header: "Onsite", className: "text-right", hideBelow: "md", cell: (i) => price(i.price_onsite, f.currency) },
    { key: "status", header: "Status", cell: (i) => (i.is_active ? <Indicator value="ACTIVE" text="Active" /> : <Indicator value="INACTIVE" text="Inactive" />) },
  ];
  if (!f.has_catalog) {
    return <EmptyState title="This form has no catalog. Turn on “Catalog of items with prices” in Settings to add items." />;
  }
  const rows = q.data?.items ?? [];
  return (
    <div>
      <PanelHeader title={q.data ? `${f.active_item_count} active of ${q.data.total} items` : "Items"} actions={actions} />
      {q.isPending ? <TableSkeleton rows={6} label="Loading catalog" /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : rows.length === 0 ? (
        <EmptyState title="No items yet. Add them one by one or import the catalog from Excel." action={actions ?? undefined} />
      ) : (
        <ListTable
          caption={`Catalog of form ${f.code}`}
          rows={rows}
          columns={columns}
          rowKey={(i) => i.id}
          rowLink={manage ? (i) => ({ to: "/app/order-forms/$formId/items/$itemId", params: { formId: f.id, itemId: i.id } }) : undefined}
        />
      )}
    </div>
  );
}
