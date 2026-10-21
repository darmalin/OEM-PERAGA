import { api, call } from "@ems/api";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { gatesQuery } from "@/features/gate/queries";
import { useEdition } from "@/lib/edition";
import { handleFormError, uuid } from "@/lib/forms";
import { label } from "@/lib/labels";
import { notifySuccess } from "@/lib/notify";
import { Button } from "@/ui/button";
import { Field, FieldGrid, Section } from "@/ui/field";
import { SearchFilter } from "@/ui/filters";
import { Indicator } from "@/ui/indicator";
import { Select, Textarea } from "@/ui/input";
import { FormActions, Page, PageHead, Panel } from "@/ui/page";
import { NoEdition } from "@/ui/states";

export const Route = createFileRoute("/app/overrides/new")({ component: ManualEntry });

function ManualEntry() {
  const { edition } = useEdition();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [q, setQ] = useState<string | undefined>();
  const [regId, setRegId] = useState<string | null>(null);
  const [key] = useState(uuid);
  const gates = useQuery({ ...gatesQuery(edition?.id ?? ""), enabled: Boolean(edition) });
  const regs = useQuery({
    queryKey: ["registrations", edition?.id, "override", q],
    enabled: Boolean(edition && q && q.length >= 2),
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET("/api/v1/visitor-registrations", { params: { query: { edition_id: edition!.id, q, page_size: 8 } } })),
  });
  const form = useForm<{ gate_id: string; reason: string }>({ defaultValues: { gate_id: "", reason: "" } });
  if (!edition) return <Page><NoEdition /></Page>;

  const onSubmit = form.handleSubmit(async (v) => {
    if (!regId) return;
    try {
      const scan = await call(api.POST("/api/v1/gate/overrides", { body: { scan_event_id: key, gate_id: v.gate_id, registration_id: regId, reason: v.reason } }));
      void queryClient.invalidateQueries({ queryKey: ["scans"] });
      notifySuccess(`${scan.first_name ?? "Visitor"} admitted`, label("scan_result", scan.result));
      await navigate({ to: "/app/scans" });
    } catch (e) {
      handleFormError(e, form.setError, ["gate_id", "reason"]);
    }
  });

  return (
    <Page className="max-w-[960px]">
      <PageHead title="Manual Entry" meta="Admit a registered visitor whose QR cannot be read. Counts as an entry and is audited." back={{ to: "/app/scans", label: "Scan History" }} />
      <Panel>
        <form onSubmit={onSubmit} noValidate>
          <Section title="Visitor">
            <SearchFilter value={q} onChange={(v) => { setQ(v); setRegId(null); }} placeholder="Name or Registration ID" label="Find a registration" />
            <ul className="mt-3 flex flex-col gap-1" role="radiogroup" aria-label="Registration">
              {(regs.data?.items ?? []).map((r) => (
                <li key={r.id}>
                  <label className="flex cursor-pointer items-center justify-between gap-3 rounded-[8px] px-3 py-2 text-[14px] hover:bg-hover has-[:checked]:bg-input has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus">
                    <span>
                      <input type="radio" name="reg" className="sr-only" checked={regId === r.id} onChange={() => setRegId(r.id)} />
                      {r.first_name} <span className="text-label tabular">{r.registration_code}</span>
                    </span>
                    <Indicator value={r.qr_status} group="qr_status" />
                  </label>
                </li>
              ))}
              {q && regs.data && regs.data.items.length === 0 ? <li className="px-3 py-2 text-[13px] text-muted">No registered visitor matches. Register them first from their lead.</li> : null}
            </ul>
          </Section>
          <Section title="Entry">
            <FieldGrid className="lg:grid-cols-2">
              <Field label="Gate" required error={form.formState.errors.gate_id?.message}>
                {(p) => (
                  <Select {...p} {...form.register("gate_id", { required: "Choose the gate." })}>
                    <option value="">Choose a gate</option>
                    {(gates.data ?? []).filter((g) => g.is_active).map((g) => <option key={g.id} value={g.id}>{g.code} · {g.name}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Reason" required error={form.formState.errors.reason?.message}>
                {(p) => <Textarea {...p} placeholder="For example: phone screen cracked, ID checked" {...form.register("reason", { required: "Give a reason for the audit log." })} />}
              </Field>
            </FieldGrid>
          </Section>
          <FormActions>
            <Button asChild variant="ghost"><Link to="/app/scans">Cancel</Link></Button>
            <Button type="submit" variant="primary" disabled={!regId} loading={form.formState.isSubmitting}>Admit Visitor</Button>
          </FormActions>
        </form>
      </Panel>
    </Page>
  );
}
