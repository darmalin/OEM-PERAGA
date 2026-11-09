import type { FieldErrors, UseFormRegister, UseFormSetValue, UseFormWatch } from "react-hook-form";

import { DETAILS_TYPES, PURPOSES, type AttachmentPurpose, type DetailsType, type OrderForm } from "@/features/order-forms/queries";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";

export interface FormValues {
  code: string;
  title: string;
  details_type: DetailsType | "";
  has_catalog: boolean;
  allow_custom_items: boolean;
  attachment_purposes: AttachmentPurpose[];
  deadline_on: string;
  closes_on: string;
  secondary_deadline_label: string;
  secondary_deadline_on: string;
  instructions: string;
  currency: string;
  sort_order: string;
  is_published: boolean;
}

export const FORM_FIELDS = [
  "code", "title", "details_type", "has_catalog", "allow_custom_items", "attachment_purposes", "deadline_on",
  "closes_on", "secondary_deadline_label", "secondary_deadline_on", "instructions", "currency", "sort_order",
  "is_published",
] as const;

export const EMPTY_FORM: FormValues = {
  code: "", title: "", details_type: "", has_catalog: true, allow_custom_items: false, attachment_purposes: [],
  deadline_on: "", closes_on: "", secondary_deadline_label: "", secondary_deadline_on: "", instructions: "",
  currency: "", sort_order: "", is_published: false,
};

export const formValues = (f: OrderForm): FormValues => ({
  code: f.code,
  title: f.title,
  details_type: f.details_type ?? "",
  has_catalog: f.has_catalog,
  allow_custom_items: f.allow_custom_items,
  attachment_purposes: f.attachment_purposes,
  deadline_on: f.deadline_on ?? "",
  closes_on: f.closes_on ?? "",
  secondary_deadline_label: f.secondary_deadline_label ?? "",
  secondary_deadline_on: f.secondary_deadline_on ?? "",
  instructions: f.instructions ?? "",
  currency: f.currency,
  sort_order: String(f.sort_order),
  is_published: f.is_published,
});

/** Body shared by create and edit; the number is sent on create only. */
export const formBody = (v: FormValues) => ({
  title: v.title.trim(),
  details_type: v.details_type || null,
  has_catalog: v.has_catalog,
  allow_custom_items: v.has_catalog && v.allow_custom_items,
  attachment_purposes: v.attachment_purposes,
  deadline_on: v.deadline_on || null,
  closes_on: v.closes_on || null,
  secondary_deadline_label: v.secondary_deadline_label.trim() || null,
  secondary_deadline_on: v.secondary_deadline_on || null,
  instructions: v.instructions.trim() || null,
  currency: v.currency.trim().toUpperCase() || null,
  sort_order: v.sort_order.trim() ? Number(v.sort_order) : 0,
  is_published: v.is_published,
});

function Check({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: string }) {
  return (
    <label className="flex items-center gap-2 text-[14px]">
      <Checkbox checked={checked} onCheckedChange={(c) => onChange(c === true)} />
      {children}
    </label>
  );
}

export function OrderFormFields({
  register,
  watch,
  setValue,
  errors,
  isNew,
}: {
  register: UseFormRegister<FormValues>;
  watch: UseFormWatch<FormValues>;
  setValue: UseFormSetValue<FormValues>;
  errors: FieldErrors<FormValues>;
  isNew: boolean;
}) {
  const set = (key: "is_published" | "has_catalog" | "allow_custom_items", value: boolean) => setValue(key, value, { shouldDirty: true });
  const purposes = watch("attachment_purposes");
  const togglePurpose = (p: AttachmentPurpose, on: boolean) =>
    setValue("attachment_purposes", on ? [...purposes, p] : purposes.filter((x) => x !== p), { shouldDirty: true });
  return (
    <>
      <Section title="Form">
        <FieldGrid>
          <Field label="Form Number" required help={isNew ? "As exhibitors know it, e.g. 04 or 02a. Cannot change later." : "Fixed once the form is created."} error={errors.code?.message}>
            {(p) => <Input {...p} disabled={!isNew} {...register("code", { required: "Enter the form number.", pattern: { value: /^\s*[0-9]{2}[a-z]?\s*$/, message: "Two digits and an optional small letter, e.g. 04 or 02a." } })} />}
          </Field>
          <Field label="Title" required className="md:col-span-2" error={errors.title?.message}>
            {(p) => <Input {...p} {...register("title", { required: "Enter the title." })} />}
          </Field>
          <Field label="Currency" help="Three letters. Empty uses the edition currency." error={errors.currency?.message}>
            {(p) => <Input {...p} maxLength={3} className="uppercase" {...register("currency", { pattern: { value: /^[A-Za-z]{3}$/, message: "Use a three-letter code, e.g. IDR." } })} />}
          </Field>
          <Field label="Order in List" help="Lower numbers come first." error={errors.sort_order?.message}>
            {(p) => <Input {...p} inputMode="numeric" {...register("sort_order", { pattern: { value: /^\d*$/, message: "Enter a whole number." } })} />}
          </Field>
          <div className="flex items-end pb-1.5">
            <Check checked={watch("is_published")} onChange={(v) => set("is_published", v)}>Published to the exhibitor portal</Check>
          </div>
        </FieldGrid>
      </Section>
      <Section title="What the Exhibitor Fills In">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-3">
            <Check checked={watch("has_catalog")} onChange={(v) => set("has_catalog", v)}>Catalog of items with prices</Check>
            <div className="pl-6">
              <Check checked={watch("has_catalog") && watch("allow_custom_items")} onChange={(v) => set("allow_custom_items", v)}>
                Extra items not in the catalog (staff set the price)
              </Check>
              {errors.allow_custom_items?.message ? <p className="mt-1 text-[12px] text-required">{errors.allow_custom_items.message}</p> : null}
            </div>
          </div>
          <Field label="Questions" help="Question sets are defined by the system." error={errors.details_type?.message}>
            {(p) => (
              <Select {...p} {...register("details_type")}>
                <option value="">None</option>
                {Object.entries(DETAILS_TYPES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </Select>
            )}
          </Field>
          <fieldset className="flex flex-col gap-2 md:col-span-2">
            <legend className="mb-1 text-[13px] text-label">Attachments</legend>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {(Object.keys(PURPOSES) as AttachmentPurpose[]).map((p) => (
                <Check key={p} checked={purposes.includes(p)} onChange={(on) => togglePurpose(p, on)}>{PURPOSES[p]}</Check>
              ))}
            </div>
          </fieldset>
        </div>
      </Section>
      <Section title="Dates">
        <FieldGrid>
          <Field label="Deadline" help="Shown with a countdown in the portal." error={errors.deadline_on?.message}>
            {(p) => <Input {...p} type="date" {...register("deadline_on")} />}
          </Field>
          <Field label="Closes On" help="Last day to submit. Empty uses the edition's Order Expired date." error={errors.closes_on?.message}>
            {(p) => <Input {...p} type="date" {...register("closes_on")} />}
          </Field>
          <div />
          <Field label="Second Deadline Label" help="Only when the form has two deadlines, e.g. Material Deadline." error={errors.secondary_deadline_label?.message}>
            {(p) => <Input {...p} {...register("secondary_deadline_label")} />}
          </Field>
          <Field label="Second Deadline" error={errors.secondary_deadline_on?.message}>
            {(p) => <Input {...p} type="date" {...register("secondary_deadline_on")} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Instructions">
        <Field label="Notes and Terms" help="Shown on the form in the portal: delivery, cancellation, and payment terms." error={errors.instructions?.message}>
          {(p) => <Textarea {...p} rows={6} {...register("instructions")} />}
        </Field>
      </Section>
    </>
  );
}
