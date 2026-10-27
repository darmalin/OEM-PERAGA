import { useQuery } from "@tanstack/react-query";
import { type Control, Controller, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { leadSourcesQuery } from "@/features/leads/queries";
import { fromLocalInput, toLocalInput } from "@/lib/format";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";

import type { CampaignLink } from "./queries";

export interface LinkValues {
  name: string;
  lead_source_id: string;
  is_active: boolean;
  starts_at: string;
  ends_at: string;
  max_submissions: string;
  gtm_container_id: string;
}

export const emptyLink: LinkValues = {
  name: "",
  lead_source_id: "",
  is_active: true,
  starts_at: "",
  ends_at: "",
  max_submissions: "",
  gtm_container_id: "",
};

export function linkValues(l: CampaignLink, timezone: string): LinkValues {
  return {
    name: l.name,
    lead_source_id: l.lead_source_id ?? "",
    is_active: l.is_active,
    starts_at: toLocalInput(l.starts_at, timezone),
    ends_at: toLocalInput(l.ends_at, timezone),
    max_submissions: l.max_submissions ? String(l.max_submissions) : "",
    gtm_container_id: l.gtm_container_id ?? "",
  };
}

/** Request body; times are typed in the edition's time zone. */
export function linkBody(v: LinkValues, timezone: string) {
  return {
    name: v.name.trim(),
    lead_source_id: v.lead_source_id || null,
    is_active: v.is_active,
    starts_at: fromLocalInput(v.starts_at, timezone),
    ends_at: fromLocalInput(v.ends_at, timezone),
    max_submissions: v.max_submissions ? Number(v.max_submissions) : null,
    gtm_container_id: v.gtm_container_id.trim() || null,
  };
}

export const LINK_FIELDS = ["name", "lead_source_id", "is_active", "starts_at", "ends_at", "max_submissions", "gtm_container_id"] as const;

export function LinkFields({
  register,
  control,
  errors,
  timezone,
  currentSourceId,
}: {
  register: UseFormRegister<LinkValues>;
  control: Control<LinkValues>;
  errors: FieldErrors<LinkValues>;
  timezone: string;
  currentSourceId?: string | null;
}) {
  const sources = useQuery(leadSourcesQuery(true));
  // Active sources, plus the link's current one even if it was switched off since.
  const sourceOptions = (sources.data ?? []).filter((s) => s.is_active || s.id === currentSourceId);
  return (
    <>
      <Section title="Campaign Link">
        <FieldGrid>
          <Field label="Name" required help="For your team only; visitors never see it. E.g. IG October, Poster Hall A." error={errors.name?.message}>
            {(p) => <Input {...p} maxLength={200} {...register("name", { required: "Enter a name." })} />}
          </Field>
          <Field label="Source" help="Given to every lead from this link." error={errors.lead_source_id?.message}>
            {(p) => (
              <Controller
                control={control}
                name="lead_source_id"
                render={({ field }) => (
                  <Select {...p} value={field.value} onChange={field.onChange}>
                    <option value="">None</option>
                    {sourceOptions.map((s) => (
                      <option key={s.id} value={s.id}>{s.is_active ? s.name : `${s.name} (inactive)`}</option>
                    ))}
                  </Select>
                )}
              />
            )}
          </Field>
          <Controller
            control={control}
            name="is_active"
            render={({ field }) => (
              <div className="flex flex-col gap-1.5">
                <span className="text-[13px] text-label">Status</span>
                <label className="flex h-8 items-center gap-2 text-[14px]">
                  <Checkbox checked={field.value} onCheckedChange={(c) => field.onChange(c === true)} />
                  Active (takes registrations)
                </label>
              </div>
            )}
          />
        </FieldGrid>
      </Section>
      <Section title="Limits">
        <FieldGrid>
          <Field label="Opens" help={`Empty: open now. Time in ${timezone}.`} error={errors.starts_at?.message}>
            {(p) => <Input {...p} type="datetime-local" {...register("starts_at")} />}
          </Field>
          <Field label="Closes" help="Empty: stays open while the edition is Active." error={errors.ends_at?.message}>
            {(p) => <Input {...p} type="datetime-local" {...register("ends_at")} />}
          </Field>
          <Field label="Maximum Registrations" help="Empty: no limit. The form closes once reached." error={errors.max_submissions?.message}>
            {(p) => <Input {...p} type="number" min={1} max={1000000} inputMode="numeric" {...register("max_submissions", { min: { value: 1, message: "Use 1 or more." } })} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Tracking">
        <FieldGrid>
          <Field
            label="Google Tag Manager ID"
            help="Format GTM-XXXXXXX. Loads your GTM container on this form only. Tags in that container run on a page where visitors type their details: keep its access limited, and test the link in a private window."
            error={errors.gtm_container_id?.message}
            className="md:col-span-2"
          >
            {(p) => (
              <Input
                {...p}
                className="uppercase"
                maxLength={20}
                placeholder="GTM-XXXXXXX"
                autoComplete="off"
                {...register("gtm_container_id", { pattern: { value: /^\s*(GTM-[A-Z0-9]{4,12})?\s*$/i, message: "Use a container ID like GTM-ABC1234." } })}
              />
            )}
          </Field>
        </FieldGrid>
      </Section>
    </>
  );
}
