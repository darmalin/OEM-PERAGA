import { api, ApiError, call, upload } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ImageUp } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { itemImageUrl, orderFormItemsQuery, orderFormQuery, type OrderFormItem } from "@/features/order-forms/queries";
import { handleFormError } from "@/lib/forms";
import { notifyError, notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

import { ITEM_FIELDS, itemBody, ItemFields, itemValues, type ItemValues } from "../-item-form";

export const Route = createFileRoute("/app/order-forms/$formId/items/$itemId")({ component: EditItem });

function EditItem() {
  const { formId, itemId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const formQ = useQuery(orderFormQuery(formId));
  const itemsQ = useQuery(orderFormItemsQuery(formId));
  const item = itemsQ.data?.items.find((i) => i.id === itemId);
  const form = useForm<ItemValues>({ values: item ? itemValues(item) : undefined });
  const back = { to: "/app/order-forms/$formId", params: { formId }, search: { tab: "catalog" as const } };
  const onSubmit = form.handleSubmit(async (v) => {
    if (!item) return;
    try {
      await call(
        api.PATCH("/api/v1/order-forms/{form_id}/items/{item_id}", {
          params: { path: { form_id: formId, item_id: itemId } },
          body: { ...itemBody(v), version: item.version },
        }),
      );
      void queryClient.invalidateQueries({ queryKey: ["order-forms"] });
      notifySuccess(`Item ${v.code.trim()} saved`, "Orders already sent keep the price they were sent with.");
      await navigate(back);
    } catch (e) {
      handleFormError(e, form.setError, ITEM_FIELDS);
    }
  });
  const pending = formQ.isPending || itemsQ.isPending;
  const error = formQ.error ?? itemsQ.error;
  const f = formQ.data;
  return (
    <Page className="max-w-[1000px]">
      <PageHead title={item ? `${item.code} · ${item.name}` : "Catalog item"} back={{ ...back, label: f ? `Form ${f.code}` : "Order form" }} />
      <Panel>
        {pending ? <FormSkeleton /> : error ? <ErrorState error={error} onRetry={() => { void formQ.refetch(); void itemsQ.refetch(); }} /> : !item || !f ? (
          <EmptyState title="Item not found in this form." />
        ) : (
          <>
            <form onSubmit={onSubmit} noValidate>
              <ItemFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} currency={f.currency} />
              <FormActions>
                <Button asChild variant="ghost"><Link {...back}>Cancel</Link></Button>
                <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Item</Button>
              </FormActions>
            </form>
            <ItemPicture formId={formId} item={item} />
          </>
        )}
      </Panel>
    </Page>
  );
}

/** Separate from the form: uploading saves at once and bumps the item's version. */
function ItemPicture({ formId, item }: { formId: string; item: OrderFormItem }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async () => {
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    body.append("version", String(item.version));
    setBusy(true);
    try {
      await upload<OrderFormItem>(`/api/v1/order-forms/${formId}/items/${item.id}/image`, body);
      await queryClient.invalidateQueries({ queryKey: ["order-forms", "form", formId, "items"] });
      setFile(null);
      notifySuccess("Picture saved");
    } catch (e) {
      if (e instanceof ApiError) setError(Object.values(e.fields)[0] ?? null);
      notifyError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Picture">
      <div className="flex flex-wrap items-end gap-6">
        {item.has_image ? (
          <img src={itemImageUrl(formId, item.id, item.version)} alt={item.name} className="h-28 w-28 rounded-[8px] border border-line object-contain" />
        ) : (
          <div className="flex h-28 w-28 items-center justify-center rounded-[8px] border border-dashed border-line text-[12px] text-label">No picture</div>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <Field label={item.has_image ? "Replace Picture" : "Picture"} error={error ?? undefined} help="JPG or PNG, up to 5 MB. Shown next to the item in the portal.">
            {(p) => <Input {...p} type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" className="py-1" onChange={(e) => { setError(null); setFile(e.target.files?.[0] ?? null); }} />}
          </Field>
          <Button type="button" disabled={!file} loading={busy} onClick={() => void send()}><ImageUp aria-hidden />Upload Picture</Button>
        </div>
      </div>
    </Section>
  );
}
