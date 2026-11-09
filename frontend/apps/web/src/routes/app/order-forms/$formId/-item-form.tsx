import type { FieldErrors, UseFormRegister, UseFormSetValue, UseFormWatch } from "react-hook-form";

import type { OrderFormItem } from "@/features/order-forms/queries";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Textarea } from "@/ui/input";

export interface ItemValues {
  section: string;
  code: string;
  name: string;
  description: string;
  size: string;
  unit: string;
  price_regular: string;
  price_surcharge: string;
  price_onsite: string;
  max_quantity: string;
  sort_order: string;
  is_active: boolean;
}

export const ITEM_FIELDS = [
  "section", "code", "name", "description", "size", "unit", "price_regular", "price_surcharge", "price_onsite",
  "max_quantity", "sort_order", "is_active",
] as const;

export const EMPTY_ITEM: ItemValues = {
  section: "", code: "", name: "", description: "", size: "", unit: "", price_regular: "", price_surcharge: "",
  price_onsite: "", max_quantity: "", sort_order: "", is_active: true,
};

export const itemValues = (i: OrderFormItem): ItemValues => ({
  section: i.section ?? "",
  code: i.code,
  name: i.name,
  description: i.description ?? "",
  size: i.size ?? "",
  unit: i.unit ?? "",
  price_regular: i.price_regular,
  price_surcharge: i.price_surcharge ?? "",
  price_onsite: i.price_onsite ?? "",
  max_quantity: i.max_quantity == null ? "" : String(i.max_quantity),
  sort_order: String(i.sort_order),
  is_active: i.is_active,
});

export const itemBody = (v: ItemValues) => ({
  section: v.section.trim() || null,
  code: v.code.trim(),
  name: v.name.trim(),
  description: v.description.trim() || null,
  size: v.size.trim() || null,
  unit: v.unit.trim() || null,
  price_regular: v.price_regular,
  price_surcharge: v.price_surcharge || null,
  price_onsite: v.price_onsite || null,
  max_quantity: v.max_quantity.trim() ? Number(v.max_quantity) : null,
  sort_order: v.sort_order.trim() ? Number(v.sort_order) : 0,
  is_active: v.is_active,
});

const AMOUNT = { value: /^\d+(\.\d{1,2})?$/, message: "Enter an amount, e.g. 740600." };

export function ItemFields({
  register,
  watch,
  setValue,
  errors,
  currency,
}: {
  register: UseFormRegister<ItemValues>;
  watch: UseFormWatch<ItemValues>;
  setValue: UseFormSetValue<ItemValues>;
  errors: FieldErrors<ItemValues>;
  currency: string;
}) {
  return (
    <>
      <Section title="Item">
        <FieldGrid>
          <Field label="Code" required help="Unique in this form, e.g. E-001." error={errors.code?.message}>
            {(p) => <Input {...p} {...register("code", { required: "Enter the item code." })} />}
          </Field>
          <Field label="Name" required className="md:col-span-2" error={errors.name?.message}>
            {(p) => <Input {...p} {...register("name", { required: "Enter the item name." })} />}
          </Field>
          <Field label="Section" help="Groups items in the portal, e.g. A. Lighting & Equipment." error={errors.section?.message}>
            {(p) => <Input {...p} {...register("section")} />}
          </Field>
          <Field label="Size" error={errors.size?.message}>{(p) => <Input {...p} {...register("size")} />}</Field>
          <Field label="Unit" help="e.g. unit, day, m²." error={errors.unit?.message}>{(p) => <Input {...p} {...register("unit")} />}</Field>
          <Field label="Description" className="md:col-span-2 lg:col-span-3" error={errors.description?.message}>
            {(p) => <Textarea {...p} {...register("description")} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title={`Prices (${currency})`}>
        <FieldGrid>
          <Field label="Regular" required error={errors.price_regular?.message}>
            {(p) => <Input {...p} inputMode="decimal" {...register("price_regular", { required: "Enter the regular price.", pattern: AMOUNT })} />}
          </Field>
          <Field label="Surcharge" help="Empty uses the regular price." error={errors.price_surcharge?.message}>
            {(p) => <Input {...p} inputMode="decimal" {...register("price_surcharge", { pattern: AMOUNT })} />}
          </Field>
          <Field label="Onsite" help="Empty uses the regular price." error={errors.price_onsite?.message}>
            {(p) => <Input {...p} inputMode="decimal" {...register("price_onsite", { pattern: AMOUNT })} />}
          </Field>
        </FieldGrid>
        <p className="mt-3 text-[12px] text-label">The period comes from the edition's price dates on the day the exhibitor submits.</p>
      </Section>
      <Section title="Ordering">
        <FieldGrid>
          <Field label="Most per Order" help="Empty means no limit." error={errors.max_quantity?.message}>
            {(p) => <Input {...p} inputMode="numeric" {...register("max_quantity", { pattern: { value: /^([1-9]\d*)?$/, message: "Enter a whole number above 0." } })} />}
          </Field>
          <Field label="Order in List" help="Lower numbers come first." error={errors.sort_order?.message}>
            {(p) => <Input {...p} inputMode="numeric" {...register("sort_order", { pattern: { value: /^\d*$/, message: "Enter a whole number." } })} />}
          </Field>
          <div className="flex items-end pb-1.5">
            <label className="flex items-center gap-2 text-[14px]">
              <Checkbox checked={watch("is_active")} onCheckedChange={(c) => setValue("is_active", c === true, { shouldDirty: true })} />
              Can be ordered
            </label>
          </div>
        </FieldGrid>
      </Section>
    </>
  );
}
