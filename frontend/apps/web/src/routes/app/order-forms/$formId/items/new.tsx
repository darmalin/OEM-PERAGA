import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { orderFormQuery } from "@/features/order-forms/queries";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { ErrorState, FormSkeleton } from "@/ui/states";

import { EMPTY_ITEM, ITEM_FIELDS, itemBody, ItemFields, type ItemValues } from "../-item-form";

export const Route = createFileRoute("/app/order-forms/$formId/items/new")({ component: NewItem });

function NewItem() {
  const { formId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery(orderFormQuery(formId));
  const form = useForm<ItemValues>({ defaultValues: EMPTY_ITEM });
  const back = { to: "/app/order-forms/$formId", params: { formId }, search: { tab: "catalog" as const } };
  const save = (another: boolean) =>
    form.handleSubmit(async (v) => {
      try {
        const item = await call(api.POST("/api/v1/order-forms/{form_id}/items", { params: { path: { form_id: formId } }, body: itemBody(v) }));
        void queryClient.invalidateQueries({ queryKey: ["order-forms"] });
        notifySuccess(`Item ${item.code} added`);
        // The next item usually sits in the same section.
        if (another) form.reset({ ...EMPTY_ITEM, section: v.section, unit: v.unit });
        else await navigate(back);
      } catch (e) {
        handleFormError(e, form.setError, ITEM_FIELDS);
      }
    })();
  const f = q.data;
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="New Catalog Item" back={{ ...back, label: f ? `Form ${f.code}` : "Order form" }} meta={f ? `Adds to ${f.code} · ${f.title}.` : undefined} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : (
          <form onSubmit={(e) => { e.preventDefault(); void save(false); }} noValidate>
            <ItemFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} currency={q.data.currency} />
            <FormActions>
              <Button asChild variant="ghost"><Link {...back}>Cancel</Link></Button>
              <Button type="button" loading={form.formState.isSubmitting} onClick={() => void save(true)}>Save and Add Another</Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Item</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
