import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { type Control, Controller, type FieldErrors, type UseFormRegister, useWatch } from "react-hook-form";

import { COUNTRIES } from "@/lib/countries";
import { options as labelOptions } from "@/lib/labels";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";

import { type CustomField, customFieldsQuery, fieldOptionsQuery, leadSourcesQuery } from "./queries";

/** Form values: every Person field the API accepts, as strings for the inputs. */
export interface PersonValues {
  lead_date: string;
  first_name: string;
  email: string;
  phone: string;
  gender: string;
  company_name: string;
  job_title: string;
  country: string;
  city: string;
  website: string;
  business_type: string;
  branch: string;
  /** "Source" (global master data); the system's intake channel is shown as "Channel". */
  lead_source_id: string;
  /** Free text since 2026-10-22, like the old system. */
  product_categories: string;
  comment: string;
  custom_fields: Record<string, unknown>;
}

export const PERSON_FIELDS = [
  "lead_date", "first_name", "email", "phone", "gender", "company_name", "job_title", "country", "city",
  "website", "business_type", "branch", "lead_source_id", "product_categories", "comment", "custom_fields",
] as const;

export function emptyPerson(): PersonValues {
  return {
    lead_date: "", first_name: "", email: "", phone: "", gender: "", company_name: "", job_title: "",
    country: "", city: "", website: "", business_type: "", branch: "", lead_source_id: "",
    product_categories: "", comment: "", custom_fields: {},
  };
}

/** Empty strings become null, so clearing a field clears it in the API. */
export function personPayload(v: PersonValues, dirty?: Partial<Record<keyof PersonValues, unknown>>) {
  const out: Record<string, unknown> = {};
  for (const key of PERSON_FIELDS) {
    if (dirty && !dirty[key]) continue;
    const value = v[key];
    out[key] = typeof value === "string" ? (value.trim() === "" ? null : value.trim()) : value;
  }
  if ("lead_date" in out && out.lead_date) out.lead_date = new Date(out.lead_date as string).toISOString();
  return out;
}

interface Props {
  editionId: string;
  register: UseFormRegister<PersonValues>;
  control: Control<PersonValues>;
  errors: FieldErrors<PersonValues>;
  readOnly?: boolean;
  /** Extra read-only cells shown in the grid, e.g. Registration ID and Status. */
  systemCells?: ReactNode;
  /** The Exhibition Type cell: the lead's edition (owner decision 2026-10-22). */
  exhibitionType: ReactNode;
}

function OptionSelect({ field, opts, ...rest }: { field: string; opts: { value: string; label: string }[] } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <Select {...rest} data-field={field}>
      <option value="">Not set</option>
      {opts.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </Select>
  );
}

/** The Person section in the screenshot's order (DESIGN.md "Form view"). */
export function PersonFields({ editionId, register, control, errors, readOnly, systemCells, exhibitionType }: Props) {
  const options = useQuery(fieldOptionsQuery(editionId));
  const custom = useQuery(customFieldsQuery(editionId));
  const sources = useQuery(leadSourcesQuery(true));
  const sourceId = useWatch({ control, name: "lead_source_id" });
  // Inactive sources are offered only to a lead that already has one.
  const sourceOpts = (sources.data ?? [])
    .filter((o) => o.is_active || o.id === sourceId)
    .map((o) => ({ value: o.id, label: o.is_active ? o.name : `${o.name} (inactive)` }));
  const opts = (field: string) =>
    (options.data ?? []).filter((o) => o.field === field && o.is_active).map((o) => ({ value: o.value, label: o.label }));
  const contactError = errors.email?.message ?? errors.phone?.message;

  return (
    <>
      <Section title="Person">
        <FieldGrid>
          <Field label="Date" help="Registration date; defaults to now.">
            {(p) => <Input {...p} type="datetime-local" readOnly={readOnly} {...register("lead_date")} />}
          </Field>
          {systemCells}
          <Field label="First Name" required error={errors.first_name?.message}>
            {(p) => <Input {...p} readOnly={readOnly} {...register("first_name", { required: "First Name is required." })} />}
          </Field>
          <Field label="Email" error={errors.email?.message} help={contactError ? undefined : "Email or Phone is required."}>
            {(p) => <Input {...p} type="email" autoComplete="off" readOnly={readOnly} {...register("email")} />}
          </Field>
          <Field label="Gender">
            {(p) => <OptionSelect {...p} field="gender" opts={labelOptions("gender")} disabled={readOnly} {...register("gender")} />}
          </Field>
          <Field label="Phone" error={errors.phone?.message} help={contactError ? undefined : "Email or Phone is required."}>
            {(p) => <Input {...p} type="tel" readOnly={readOnly} {...register("phone")} />}
          </Field>
          <Field label="Company Name">
            {(p) => <Input {...p} readOnly={readOnly} {...register("company_name")} />}
          </Field>
          <Field label="Source" error={errors.lead_source_id?.message}>
            {/* Controlled: the options load after the form values, so the select follows the form. */}
            {(p) => <OptionSelect {...p} field="lead_source_id" opts={sourceOpts} disabled={readOnly} {...register("lead_source_id")} value={sourceId} />}
          </Field>
          <Field label="Job Title">
            {(p) => <Input {...p} readOnly={readOnly} {...register("job_title")} />}
          </Field>
          <Field label="Country">
            {(p) => <OptionSelect {...p} field="country" opts={COUNTRIES} disabled={readOnly} {...register("country")} />}
          </Field>
          <Field label="City">
            {(p) => <Input {...p} readOnly={readOnly} {...register("city")} />}
          </Field>
          <Field label="Website" error={errors.website?.message}>
            {(p) => <Input {...p} readOnly={readOnly} placeholder="example.com" {...register("website")} />}
          </Field>
          <Field label="Business Type">
            {(p) => <OptionSelect {...p} field="business_type" opts={opts("BUSINESS_TYPE")} disabled={readOnly} {...register("business_type")} />}
          </Field>
          <Field label="Branch">
            {(p) => <OptionSelect {...p} field="branch" opts={opts("BRANCH")} disabled={readOnly} {...register("branch")} />}
          </Field>
          {exhibitionType}
          <Field label="Product Categories Interested In" error={errors.product_categories?.message}>
            {(p) => <Textarea {...p} readOnly={readOnly} maxLength={2000} {...register("product_categories")} />}
          </Field>
          <Field label="Comment" className="md:col-span-2 lg:col-span-1">
            {(p) => <Textarea {...p} readOnly={readOnly} {...register("comment")} />}
          </Field>
        </FieldGrid>
      </Section>
      {custom.data && custom.data.some((f) => f.is_active) ? (
        <Section title="Custom Fields">
          <FieldGrid>
            {custom.data
              .filter((f) => f.is_active)
              .map((f) => (
                <CustomInput key={f.id} def={f} register={register} control={control} error={(errors.custom_fields as Record<string, { message?: string }> | undefined)?.[f.field_key]?.message} readOnly={readOnly} />
              ))}
          </FieldGrid>
        </Section>
      ) : null}
    </>
  );
}

function CustomInput({ def, register, control, error, readOnly }: { def: CustomField; register: UseFormRegister<PersonValues>; control: Control<PersonValues>; error?: string; readOnly?: boolean }) {
  const name = `custom_fields.${def.field_key}` as const;
  return (
    <Field label={def.label} required={def.required} error={error}>
      {(p) => {
        switch (def.field_type) {
          case "textarea":
            return <Textarea {...p} readOnly={readOnly} {...register(name)} />;
          case "number":
            return <Input {...p} type="number" readOnly={readOnly} {...register(name, { setValueAs: (v) => (v === "" ? null : Number(v)) })} />;
          case "date":
            return <Input {...p} type="date" readOnly={readOnly} {...register(name)} />;
          case "select":
            return <OptionSelect {...p} field={def.field_key} opts={def.options.map((o) => ({ value: o, label: o }))} disabled={readOnly} {...register(name)} />;
          case "checkbox":
            return (
              <Controller
                control={control}
                name={name}
                render={({ field }) => (
                  <label className="flex h-8 items-center gap-2 text-[13px]">
                    <Checkbox id={p.id} checked={field.value === true} disabled={readOnly} onCheckedChange={(v) => field.onChange(v === true)} />
                    Yes
                  </label>
                )}
              />
            );
          case "multi_select":
            return (
              <Controller
                control={control}
                name={name}
                render={({ field }) => {
                  const value = Array.isArray(field.value) ? (field.value as string[]) : [];
                  return (
                    <div id={p.id} role="group" className="flex flex-col gap-2 rounded-[8px] bg-input p-3">
                      {def.options.map((o) => (
                        <label key={o} className="flex items-center gap-2 text-[13px]">
                          <Checkbox checked={value.includes(o)} disabled={readOnly} onCheckedChange={(v) => field.onChange(v === true ? [...value, o] : value.filter((x) => x !== o))} />
                          {o}
                        </label>
                      ))}
                    </div>
                  );
                }}
              />
            );
          default:
            return <Input {...p} readOnly={readOnly} {...register(name)} />;
        }
      }}
    </Field>
  );
}
