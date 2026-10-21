import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton } from "@/ui/states";

import { venueBody, VenueFields, type VenueValues } from "./-form";

export const Route = createFileRoute("/app/venues/$venueId")({ component: EditVenue });

function EditVenue() {
  const { venueId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const q = useQuery({ queryKey: ["venues"], queryFn: () => call(api.GET("/api/v1/venues")) });
  const venue = q.data?.find((v) => v.id === venueId);
  const form = useForm<VenueValues>({ values: venue ? { name: venue.name, address: venue.address ?? "", city: venue.city ?? "", country: venue.country ?? "" } : undefined });
  const onSubmit = form.handleSubmit(async (v) => {
    if (!venue) return;
    try {
      await call(api.PATCH("/api/v1/venues/{venue_id}", { params: { path: { venue_id: venueId } }, body: { ...venueBody(v), version: venue.version } }));
      void queryClient.invalidateQueries({ queryKey: ["venues"] });
      notifySuccess("Venue saved");
      await navigate({ to: "/app/venues" });
    } catch (e) {
      handleFormError(e, form.setError, ["name"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title={venue?.name ?? "Venue"} back={{ to: "/app/venues", label: "Venues" }} />
      <Panel>
        {q.isPending ? <FormSkeleton /> : !venue ? <EmptyState title="Venue not found." /> : (
          <form onSubmit={onSubmit} noValidate>
            <VenueFields register={form.register} errors={form.formState.errors} />
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/venues">Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Venue</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
