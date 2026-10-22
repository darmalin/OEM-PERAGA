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
 * Verification sent with a call (FEATURES/07). Answered: Lead Quality Valid and Attend required.
 * Not answered: Lead Quality only (required when the lead moves); the rest is disabled.
 */
export function CallVerificationFields({
  answered,
  qualityRequired,
  register,
  control,
  errors,
}: {
  answered: boolean;
  qualityRequired: boolean;
  register: UseFormRegister<MoveValues>;
  control: Control<MoveValues>;
  errors: FieldErrors<MoveValues>;
}) {
  return (
    <Section title="Verification">
      <FieldGrid>
        <fieldset className="flex flex-col gap-2" aria-describedby={errors.lead_quality ? "lead-quality-error" : undefined}>
          <legend className="mb-1.5 text-[13px] text-label">
            Lead Quality{qualityRequired ? <span className="text-required" aria-hidden> *</span> : null}
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
                    !q && qualityRequired ? "Choose the Lead Quality." : answered && q && q !== "VALID" ? "An answered call needs Valid." : true,
                })}
              />
              {label("validity", v)}
            </label>
          ))}
          <p className="text-[12px] text-label">
            Whether the phone or email reached the visitor.{qualityRequired ? "" : " Optional: the status stays as it is."}
          </p>
          {errors.lead_quality ? <p id="lead-quality-error" className="text-[12px] text-required">{errors.lead_quality.message}</p> : null}
        </fieldset>
        <div className="flex flex-col gap-4">
          <Field label="Attend" required={answered} error={errors.attend?.message} help={answered ? undefined : "Only after the visitor answers."}>
            {(p) => (
              <Select {...p} disabled={!answered} {...register("attend", { validate: (a) => (answered && !a ? "Attend is required for an answered call." : true) })}>
                <option value="">Not set</option>
                {options("attend").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Type of Buyers">
            {(p) => (
              <Select {...p} disabled={!answered} {...register("buyer_type")}>
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
            <label className="flex h-8 items-center gap-2 text-[14px] has-[:disabled]:text-label">
              <Checkbox checked={field.value === true} disabled={!answered} onCheckedChange={(v) => field.onChange(v === true)} />
              B2B Matching
            </label>
          )}
        />
      </FieldGrid>
    </Section>
  );
}
