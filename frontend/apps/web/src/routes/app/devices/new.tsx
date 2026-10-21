import { api, call } from "@ems/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";

import { gatesQuery } from "@/features/gate/queries";
import { useEdition } from "@/lib/edition";
import { handleFormError } from "@/lib/forms";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { EmptyState, NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/devices/new")({ component: NewDevice });

function NewDevice() {
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const form = useForm<{ gate_id: string; name: string }>({ defaultValues: { gate_id: "", name: "" } });
  if (!edition) return <Page><NoEdition /></Page>;
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      const d = await call(api.POST("/api/v1/gate/devices", { body: v }));
      void queryClient.invalidateQueries({ queryKey: ["devices"] });
      // The code exists only in this response; hand it to the next page without the URL.
      await navigate({ to: "/app/devices/$deviceId", params: { deviceId: d.id }, state: { activationCode: d.activation_code } });
    } catch (e) {
      handleFormError(e, form.setError, ["gate_id", "name"]);
    }
  });
  const open = (gates.data ?? []).filter((g) => g.is_active);
  return (
    <Page className="max-w-[860px]">
      <PageHead title="Register Scanner Device" meta="You get a one-time activation code to type on the phone." back={{ to: "/app/devices", label: "Devices" }} />
      <Panel>
        {gates.data && open.length === 0 ? (
          <EmptyState title="There is no open gate yet. Add a gate first." action={<Button asChild variant="primary"><Link to="/app/gates/new">Add Gate</Link></Button>} />
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <Section title="Device">
              <FieldGrid className="lg:grid-cols-2">
                <Field label="Gate" required error={form.formState.errors.gate_id?.message}>
                  {(p) => (
                    <Select {...p} {...form.register("gate_id", { required: "Choose a gate." })}>
                      <option value="">Choose a gate</option>
                      {open.map((g) => <option key={g.id} value={g.id}>{g.code} · {g.name}</option>)}
                    </Select>
                  )}
                </Field>
                <Field label="Device name" required help="Something staff can recognise, e.g. Gate A phone 2." error={form.formState.errors.name?.message}>
                  {(p) => <Input {...p} {...form.register("name", { required: "Enter a name." })} />}
                </Field>
              </FieldGrid>
            </Section>
            <FormActions>
              <Button asChild variant="ghost"><Link to="/app/devices">Cancel</Link></Button>
              <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>Create Activation Code</Button>
            </FormActions>
          </form>
        )}
      </Panel>
    </Page>
  );
}
