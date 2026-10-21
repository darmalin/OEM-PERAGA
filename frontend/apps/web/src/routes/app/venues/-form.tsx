import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { COUNTRIES } from "@/lib/countries";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";

export interface VenueValues {
  name: string;
  address: string;
  city: string;
  country: string;
}

export function VenueFields({ register, errors }: { register: UseFormRegister<VenueValues>; errors: FieldErrors<VenueValues> }) {
  return (
    <Section title="Venue">
      <FieldGrid>
        <Field label="Name" required error={errors.name?.message}>{(p) => <Input {...p} {...register("name", { required: "Enter a name." })} />}</Field>
        <Field label="City">{(p) => <Input {...p} {...register("city")} />}</Field>
        <Field label="Country">
          {(p) => (
            <Select {...p} {...register("country")}>
              <option value="">Not set</option>
              {COUNTRIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Address" className="md:col-span-2 lg:col-span-3">{(p) => <Textarea {...p} {...register("address")} />}</Field>
      </FieldGrid>
    </Section>
  );
}

export const venueBody = (v: VenueValues) => ({
  name: v.name.trim(),
  address: v.address.trim() || null,
  city: v.city.trim() || null,
  country: v.country || null,
});
