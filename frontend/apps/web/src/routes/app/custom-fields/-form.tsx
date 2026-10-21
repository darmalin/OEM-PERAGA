import type { FieldErrors, UseFormRegister, UseFormSetValue, UseFormWatch } from "react-hook-form";

import { options } from "@/lib/labels";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select, Textarea } from "@/ui/input";

export interface CustomFieldValues {
  field_key: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string;
  sort_order: string;
  is_active: boolean;
  in_import: boolean;
  in_export: boolean;
}

export const customFieldBody = (v: CustomFieldValues) => ({
  label: v.label.trim(),
  required: v.required,
  options: v.options.split("\n").map((o) => o.trim()).filter(Boolean),
  sort_order: Number(v.sort_order || 0),
  is_active: v.is_active,
  in_import: v.in_import,
  in_export: v.in_export,
});

export function CustomFieldFields({ register, watch, setValue, errors, creating }: { register: UseFormRegister<CustomFieldValues>; watch: UseFormWatch<CustomFieldValues>; setValue: UseFormSetValue<CustomFieldValues>; errors: FieldErrors<CustomFieldValues>; creating: boolean }) {
  const type = watch("field_type");
  const flag = (name: "required" | "is_active" | "in_import" | "in_export", text: string) => (
    <label className="flex items-center gap-2 text-[14px]">
      <Checkbox checked={watch(name)} onCheckedChange={(c) => setValue(name, c === true, { shouldDirty: true })} />
      {text}
    </label>
  );
  return (
    <Section title="Field">
      <FieldGrid>
        <Field label="Label" required error={errors.label?.message}>{(p) => <Input {...p} {...register("label", { required: "Enter a label." })} />}</Field>
        <Field label="Key" required help={creating ? "Lowercase letters, digits, and underscores. Cannot change later." : "Cannot change."} error={errors.field_key?.message}>
          {(p) => <Input {...p} readOnly={!creating} className={creating ? "" : "text-muted"} {...register("field_key", { required: "Enter a key.", pattern: { value: /^[a-z][a-z0-9_]{0,49}$/, message: "Use lowercase letters, digits, and underscores, starting with a letter." } })} />}
        </Field>
        <Field label="Type" required help={creating ? undefined : "Cannot change."}>
          {(p) => (
            <Select {...p} disabled={!creating} {...register("field_type")}>
              {options("field_type").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </Select>
          )}
        </Field>
        {type === "select" || type === "multi_select" ? (
          <Field label="Options" required help="One option per line." error={errors.options?.message} className="md:col-span-2">
            {(p) => <Textarea {...p} {...register("options", { validate: (v) => v.trim() !== "" || "Add at least one option." })} />}
          </Field>
        ) : null}
        <Field label="Sort Order" help="Lower comes first.">{(p) => <Input {...p} type="number" {...register("sort_order")} />}</Field>
        <div className="flex flex-col gap-2 pt-1">
          {flag("required", "Required")}
          {flag("is_active", "Shown on the lead form")}
          {flag("in_import", "Accepted in Excel imports")}
          {flag("in_export", "Included in exports")}
        </div>
      </FieldGrid>
    </Section>
  );
}
