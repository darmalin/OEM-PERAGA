import type { ReactNode } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Textarea } from "@/ui/input";

export interface ExhibitorLeadValues {
  /** Only the new-lead form edits it; a lead never changes edition. */
  edition_id: string;
  company_name: string;
  contact_name: string;
  email: string;
  phone: string;
  product_categories: string;
  booth_preference: string;
  budget_estimate: string;
  notes: string;
}

export const LEAD_FIELDS = [
  "company_name", "contact_name", "email", "phone", "product_categories", "booth_preference", "budget_estimate", "notes",
] as const;

export const emptyLead: ExhibitorLeadValues = {
  edition_id: "", company_name: "", contact_name: "", email: "", phone: "", product_categories: "", booth_preference: "", budget_estimate: "", notes: "",
};

/** Empty text is sent as null so a cleared field is cleared on the server too. */
export function leadBody(v: ExhibitorLeadValues) {
  const text = (s: string) => s.trim() || null;
  return {
    company_name: v.company_name.trim(),
    contact_name: v.contact_name.trim(),
    email: v.email.trim(),
    phone: text(v.phone),
    product_categories: text(v.product_categories),
    booth_preference: text(v.booth_preference),
    budget_estimate: text(v.budget_estimate),
    notes: text(v.notes),
  };
}

export function ExhibitorLeadFields({
  register,
  errors,
  readOnly,
  edition,
}: {
  register: UseFormRegister<ExhibitorLeadValues>;
  errors: FieldErrors<ExhibitorLeadValues>;
  readOnly?: boolean;
  edition: ReactNode;
}) {
  return (
    <>
      <Section title="Company">
        <FieldGrid>
          <Field label="Company Name" required error={errors.company_name?.message}>
            {(p) => <Input {...p} readOnly={readOnly} {...register("company_name", { required: "Enter the company name." })} />}
          </Field>
          <Field label="Contact Name" required error={errors.contact_name?.message}>
            {(p) => <Input {...p} readOnly={readOnly} {...register("contact_name", { required: "Enter the contact name." })} />}
          </Field>
          {edition}
          <Field label="Email" required error={errors.email?.message}>
            {(p) => <Input {...p} type="email" readOnly={readOnly} {...register("email", { required: "Enter an email address." })} />}
          </Field>
          <Field label="Phone" error={errors.phone?.message}>
            {(p) => <Input {...p} type="tel" readOnly={readOnly} {...register("phone")} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Sales">
        <FieldGrid>
          <Field label="Budget Estimate" help="In the edition currency." error={errors.budget_estimate?.message}>
            {(p) => <Input {...p} inputMode="decimal" readOnly={readOnly} {...register("budget_estimate", { pattern: { value: /^\d+(\.\d{1,2})?$/, message: "Enter an amount, e.g. 25000000." } })} />}
          </Field>
          <Field label="Product Categories" className="md:col-span-2" error={errors.product_categories?.message}>
            {(p) => <Textarea {...p} readOnly={readOnly} {...register("product_categories")} />}
          </Field>
          <Field label="Booth Preference" className="md:col-span-2 lg:col-span-3" help="Size, location, or hall the exhibitor asked for." error={errors.booth_preference?.message}>
            {(p) => <Textarea {...p} readOnly={readOnly} {...register("booth_preference")} />}
          </Field>
          <Field label="Notes" className="md:col-span-2 lg:col-span-3" error={errors.notes?.message}>
            {(p) => <Textarea {...p} readOnly={readOnly} {...register("notes")} />}
          </Field>
        </FieldGrid>
      </Section>
    </>
  );
}
