import { Controller, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { label, options } from "@/lib/labels";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Select } from "@/ui/input";

/** The Log Call / move form: the call, then the verification that comes with it. */
export interface MoveValues {
  target: string;
  call_result: string;
  called_at: string;
  duration_minutes: string;
  notes: string;
  next_followup_at: string;
  lead_quality: "VALID" | "INVALID" | "UNDECIDED" | "";
  attend: string;
  buyer_type: string;
  b2b_matching: boolean;
}

/**
 * Verification sent with every move (owner decision 2026-10-22). Answered: Lead Quality must be
 * Valid and Attend is required. Not answered: any Lead Quality, Attend optional.
 */
export function CallVerificationFields({
  answered,
  register,
  control,
  errors,
}: {
  answered: boolean;
  register: UseFormRegister<MoveValues>;
  control: Control<MoveValues>;
  errors: FieldErrors<MoveValues>;
}) {
  return (
    <Section title="Verification">
      <FieldGrid>
        <fieldset className="flex flex-col gap-2" aria-describedby={errors.lead_quality ? "lead-quality-error" : undefined}>
          <legend className="mb-1.5 text-[13px] text-label">
            Lead Quality<span className="text-required" aria-hidden> *</span>
          </legend>
          {(["VALID", "INVALID", "UNDECIDED"] as const).map((v) => (
            <label key={v} className="flex items-center gap-2 text-[14px] has-[:disabled]:text-label">
              <input
                type="radio"
                value={v}
                disabled={answered && v !== "VALID"}
                className="size-4 accent-[var(--primary)]"
                {...register("lead_quality", {
                  validate: (q) =>
                    !q ? "Choose the Lead Quality." : answered && q !== "VALID" ? "An answered call needs Valid." : true,
                })}
              />
              {label("validity", v)}
            </label>
          ))}
          <p className="text-[12px] text-label">Whether the phone or email reached the visitor.</p>
          {errors.lead_quality ? <p id="lead-quality-error" className="text-[12px] text-required">{errors.lead_quality.message}</p> : null}
        </fieldset>
        <div className="flex flex-col gap-4">
          <Field label="Attend" required={answered} error={errors.attend?.message} help={answered ? undefined : "Optional when the call was not answered."}>
            {(p) => (
              <Select {...p} {...register("attend", { validate: (a) => (answered && !a ? "Attend is required for an answered call." : true) })}>
                <option value="">Not set</option>
                {options("attend").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Type of Buyers">
            {(p) => (
              <Select {...p} {...register("buyer_type")}>
                <option value="">Not set</option>
                {options("buyer_type").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            )}
          </Field>
        </div>
        <Controller
          control={control}
          name="b2b_matching"
          render={({ field }) => (
            <label className="flex h-8 items-center gap-2 text-[14px]">
              <Checkbox checked={field.value === true} onCheckedChange={(v) => field.onChange(v === true)} />
              B2B Matching
            </label>
          )}
        />
      </FieldGrid>
    </Section>
  );
}
