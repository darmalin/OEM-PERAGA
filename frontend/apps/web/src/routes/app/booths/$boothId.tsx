import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { boothsQuery } from "@/features/exhibitors/queries";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, ErrorState, FormSkeleton } from "@/ui/states";

import { BOOTH_FIELDS, boothBody, BoothFields, type BoothValues } from "./-form";

export const Route = createFileRoute("/app/booths/$boothId")({ component: EditBooth });

function EditBooth() {
  const { boothId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { edition } = useEdition();
  const q = useQuery({ ...boothsQuery(edition?.id ?? "", { include_inactive: true }), enabled: Boolean(edition) });
  const booth = q.data?.items.find((b) => b.id === boothId);
  const form = useForm<BoothValues>({
    values: booth ? { code: booth.code, hall: booth.hall ?? "", area_sqm: booth.area_sqm, price: booth.price, currency: booth.currency, is_active: booth.is_active, notes: booth.notes ?? "" } : undefined,
  });
  const onSubmit = form.handleSubmit(async (v) => {
    if (!booth) return;
    try {
      await call(api.PATCH("/api/v1/booths/{booth_id}", { params: { path: { booth_id: boothId } }, body: { ...boothBody(v), version: booth.version } }));
      void queryClient.invalidateQueries({ queryKey: ["booths"] });
      notifySuccess(`Booth ${v.code.trim()} saved`);
      await navigate({ to: "/app/booths" });
    } catch (e) {
      handleFormError(e, form.setError, BOOTH_FIELDS);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead
        title={booth ? `Booth ${booth.code}` : "Booth"}
        back={{ to: "/app/booths", label: "Booths" }}
        meta={booth && !booth.is_available ? (booth.exhibitor_company_name ? `Held by ${booth.exhibitor_company_name}. Its price change reaches a Draft contract only when the booth is assigned again.` : "Held by a lead.") : undefined}
      />
      <Panel>
        {q.isPending ? <FormSkeleton /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : !booth ? <EmptyState title="Booth not found in this edition." /> : (
          <form onSubmit={onSubmit} noValidate>
            <BoothFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} />
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/booths">Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Booth</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
