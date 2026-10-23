import { type Control, Controller, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input } from "@/ui/input";

export interface SourceValues {
  name: string;
  sort_order: string;
  is_active: boolean;
}

export function SourceFields({ register, control, errors }: { register: UseFormRegister<SourceValues>; control: Control<SourceValues>; errors: FieldErrors<SourceValues> }) {
  return (
    <Section title="Source">
      <FieldGrid>
        <Field label="Name" required help="Shown in the Source select on every visitor lead." error={errors.name?.message}>
          {(p) => <Input {...p} maxLength={100} {...register("name", { required: "Enter a name." })} />}
        </Field>
        <Field label="Sort Order" help="Lower numbers come first." error={errors.sort_order?.message}>
          {(p) => <Input {...p} type="number" min={0} max={10000} {...register("sort_order")} />}
        </Field>
        <Controller
          control={control}
          name="is_active"
          render={({ field }) => (
            <div className="flex flex-col gap-1.5">
              <span className="text-[13px] text-label">Status</span>
              <label className="flex h-8 items-center gap-2 text-[14px]">
                <Checkbox checked={field.value} onCheckedChange={(c) => field.onChange(c === true)} />
                Active (inactive sources stay on existing leads)
              </label>
            </div>
          )}
        />
      </FieldGrid>
    </Section>
  );
}

export const sourceBody = (v: SourceValues) => ({
  name: v.name.trim(),
  sort_order: Number(v.sort_order || 0),
  is_active: v.is_active,
});
