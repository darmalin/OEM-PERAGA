import type { FieldErrors, UseFormRegister, UseFormSetValue, UseFormWatch } from "react-hook-form";

import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Textarea } from "@/ui/input";

export interface BoothValues {
  code: string;
  hall: string;
  area_sqm: string;
  price: string;
  currency: string;
  is_active: boolean;
  notes: string;
}

export const BOOTH_FIELDS = ["code", "hall", "area_sqm", "price", "currency", "is_active", "notes"] as const;

const AMOUNT = /^\d+(\.\d{1,2})?$/;

export const boothBody = (v: BoothValues) => ({
  code: v.code.trim(),
  hall: v.hall.trim() || null,
  area_sqm: v.area_sqm,
  price: v.price,
  currency: v.currency.trim().toUpperCase() || null,
  is_active: v.is_active,
  notes: v.notes.trim() || null,
});

export function BoothFields({
  register,
  watch,
  setValue,
  errors,
}: {
  register: UseFormRegister<BoothValues>;
  watch: UseFormWatch<BoothValues>;
  setValue: UseFormSetValue<BoothValues>;
  errors: FieldErrors<BoothValues>;
}) {
  return (
    <Section title="Booth">
      <FieldGrid>
        <Field label="Code" required help="As on the floor plan, e.g. A01." error={errors.code?.message}>
          {(p) => <Input {...p} {...register("code", { required: "Enter the booth code." })} />}
        </Field>
        <Field label="Hall" error={errors.hall?.message}>{(p) => <Input {...p} {...register("hall")} />}</Field>
        <Field label="Area (m²)" required error={errors.area_sqm?.message}>
          {(p) => <Input {...p} inputMode="decimal" {...register("area_sqm", { required: "Enter the area.", pattern: { value: AMOUNT, message: "Enter a number, e.g. 9 or 12.5." } })} />}
        </Field>
        <Field label="Price" required help="Copied into the contract when an exhibitor converts." error={errors.price?.message}>
          {(p) => <Input {...p} inputMode="decimal" {...register("price", { required: "Enter the price.", pattern: { value: AMOUNT, message: "Enter an amount, e.g. 15000000." } })} />}
        </Field>
        <Field label="Currency" help="Three letters. Empty uses the edition currency." error={errors.currency?.message}>
          {(p) => <Input {...p} maxLength={3} className="uppercase" {...register("currency", { pattern: { value: /^[A-Za-z]{3}$/, message: "Use a three-letter code, e.g. IDR." } })} />}
        </Field>
        <div className="flex items-end pb-1.5">
          <label className="flex items-center gap-2 text-[14px]">
            <Checkbox checked={watch("is_active")} onCheckedChange={(c) => setValue("is_active", c === true, { shouldDirty: true })} />
            Can be sold
          </label>
        </div>
        <Field label="Notes" className="md:col-span-2 lg:col-span-3" error={errors.notes?.message}>{(p) => <Textarea {...p} {...register("notes")} />}</Field>
      </FieldGrid>
    </Section>
  );
}
