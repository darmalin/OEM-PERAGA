import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { gatesQuery } from "@/features/gate/queries";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, FormSkeleton, NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/gates/$gateId")({ component: EditGate });

function EditGate() {
  const { gateId } = Route.useParams();
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const gate = gates.data?.find((g) => g.id === gateId);
  const form = useForm<{ name: string; is_active: boolean }>({ values: gate ? { name: gate.name, is_active: gate.is_active } : undefined });
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    if (!gate) return;
    try {
      await call(api.PATCH("/api/v1/gates/{gate_id}", { params: { path: { gate_id: gateId } }, body: { version: gate.version, ...v } }));
      void queryClient.invalidateQueries({ queryKey: ["gates"] });
      notifySuccess("Gate saved");
      await navigate({ to: "/app/gates" });
    } catch (e) {
      handleFormError(e, form.setError, ["name"]);
    }
  });
  return (
    <Page className="max-w-[860px]">
      <PageHead title={gate ? `Gate ${gate.code}` : "Gate"} back={{ to: "/app/gates", label: "Gates" }} />
      <Panel>
        {gates.isPending ? <FormSkeleton /> : !gate ? <EmptyState title="This gate is not in the selected edition." /> : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Gate">
              <FieldGrid className="lg:grid-cols-2">
                <Field label="Name" required error={form.formState.errors.name?.message}>
                  {(p) => <Input {...p} {...form.register("name", { required: "Enter a name." })} />}
                </Field>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[13px] text-label">Status</span>
                  <label className="flex h-8 items-center gap-2 text-[14px]">
                    <Checkbox checked={form.watch("is_active")} onCheckedChange={(c) => form.setValue("is_active", c === true, { shouldDirty: true })} />
                    Open. Closed gates reject every scan.
                  </label>
                </div>
              </FieldGrid>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/gates">Cancel</Link></Button>
              <Button type="submit" variant="primary" disabled={!form.formState.isDirty} loading={form.formState.isSubmitting}>Save Gate</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
