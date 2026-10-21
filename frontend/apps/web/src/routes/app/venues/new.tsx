import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";

import { venueBody, VenueFields, type VenueValues } from "./-form";

export const Route = createFileRoute("/app/venues/new")({ component: NewVenue });

function NewVenue() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const form = useForm<VenueValues>({ defaultValues: { name: "", address: "", city: "", country: "" } });
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await call(api.POST("/api/v1/venues", { body: venueBody(v) }));
      void queryClient.invalidateQueries({ queryKey: ["venues"] });
      notifySuccess("Venue added");
      await navigate({ to: "/app/venues" });
    } catch (e) {
      handleFormError(e, form.setError, ["name"]);
    }
  });
  return (
    <Page className="max-w-[1000px]">
      <PageHead title="New Venue" back={{ to: "/app/venues", label: "Venues" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <VenueFields register={form.register} errors={form.formState.errors} />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/venues">Cancel</Link></Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Venue</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
