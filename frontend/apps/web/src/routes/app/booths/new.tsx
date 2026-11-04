import { api, call } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

import { BOOTH_FIELDS, boothBody, BoothFields, type BoothValues } from "./-form";

export const Route = createFileRoute("/app/booths/new")({ component: NewBooth });

function NewBooth() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { edition } = useEdition();
  const form = useForm<BoothValues>({ defaultValues: { code: "", hall: "", area_sqm: "", price: "", currency: "", is_active: true, notes: "" } });
  const save = (another: boolean) =>
    form.handleSubmit(async (v) => {
      if (!edition) return;
      try {
        const booth = await call(api.POST("/api/v1/booths", { body: { ...boothBody(v), edition_id: edition.id } }));
        void queryClient.invalidateQueries({ queryKey: ["booths"] });
        notifySuccess(`Booth ${booth.code} added`);
        if (another) form.reset({ ...v, code: "", notes: "" });
        else await navigate({ to: "/app/booths" });
      } catch (e) {
        handleFormError(e, form.setError, BOOTH_FIELDS);
      }
    })();
  if (!edition) return <Page><NoEdition /></Page>;
  return (
    <Page className="max-w-[1000px]">
      <PageHead edition title="New Booth" back={{ to: "/app/booths", label: "Booths" }} meta={`Adds to ${edition.code}.`} />
      <Panel>
        <form onSubmit={(e) => { e.preventDefault(); void save(false); }} noValidate>
          <BoothFields register={form.register} watch={form.watch} setValue={form.setValue} errors={form.formState.errors} />
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/booths">Cancel</Link></Button>
            <Button type="button" loading={form.formState.isSubmitting} onClick={() => void save(true)}>Save and Add Another</Button>
            <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Save Booth</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
