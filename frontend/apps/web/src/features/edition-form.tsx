import { api, call } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import type { FieldErrors, UseFormRegister, UseFormSetValue, UseFormWatch } from "react-hook-form";

import { COUNTRIES } from "@/lib/countries";
import { options } from "@/lib/labels";
import { Checkbox } from "@/ui/checkbox";
import { Field, FieldGrid, Section } from "@/ui/field";
import { Input, Select } from "@/ui/input";

export interface EditionValues {
  exhibition_id: string;
  year: string;
  name: string;
  start_date: string;
  end_date: string;
  venue_id: string;
  country: string;
  city: string;
  timezone: string;
  default_currency: string;
  status: string;
  email_sender_name: string;
  email_reply_to: string;
  public_registration_open: boolean;
  scanner_cache_ttl_minutes: string;
}

const TIMEZONES: string[] = (() => {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return ["Asia/Jakarta", "Asia/Ho_Chi_Minh", "Asia/Singapore", "UTC"];
  }
})();

export function editionPayload(v: EditionValues) {
  const blank = (s: string) => (s.trim() === "" ? null : s.trim());
  return {
    name: blank(v.name),
    start_date: v.start_date,
    end_date: v.end_date,
    venue_id: blank(v.venue_id),
    country: blank(v.country),
    city: blank(v.city),
    timezone: v.timezone,
    default_currency: v.default_currency.trim().toUpperCase(),
    email_sender_name: blank(v.email_sender_name),
    email_reply_to: blank(v.email_reply_to),
    public_registration_open: v.public_registration_open,
    scanner_cache_ttl_minutes: v.scanner_cache_ttl_minutes ? Number(v.scanner_cache_ttl_minutes) : null,
  };
}

export function EditionFields({
  register,
  watch,
  setValue,
  errors,
  creating,
  readOnly,
}: {
  register: UseFormRegister<EditionValues>;
  watch: UseFormWatch<EditionValues>;
  setValue: UseFormSetValue<EditionValues>;
  errors: FieldErrors<EditionValues>;
  creating: boolean;
  readOnly?: boolean;
}) {
  const exhibitions = useQuery({
    queryKey: ["exhibitions", "all"],
    enabled: creating,
    queryFn: () => call(api.GET("/api/v1/exhibitions", { params: { query: { page_size: 500 } } })),
  });
  const venues = useQuery({ queryKey: ["venues"], queryFn: () => call(api.GET("/api/v1/venues")) });
  return (
    <>
      <Section title="Edition">
        <FieldGrid>
          {creating ? (
            <>
              <Field label="Exhibition" required error={errors.exhibition_id?.message}>
                {(p) => (
                  <Select {...p} {...register("exhibition_id", { required: "Choose the exhibition." })}>
                    <option value="">Choose an exhibition</option>
                    {(exhibitions.data?.items ?? []).map((e) => <option key={e.id} value={e.id}>{e.code} · {e.name}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Year" required help="One edition per exhibition per year." error={errors.year?.message}>
                {(p) => <Input {...p} type="number" min={2000} max={2100} {...register("year", { required: "Enter the year." })} />}
              </Field>
            </>
          ) : (
            <Field label="Status">
              {(p) => (
                <Select {...p} disabled={readOnly} {...register("status")}>
                  {options("edition_status").map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              )}
            </Field>
          )}
          <Field label="Name" help={creating ? "Defaults to the edition code." : undefined} error={errors.name?.message}>
            {(p) => <Input {...p} readOnly={readOnly} {...register("name")} />}
          </Field>
          <Field label="Start Date" required error={errors.start_date?.message}>
            {(p) => <Input {...p} type="date" readOnly={readOnly} {...register("start_date", { required: "Choose the first day." })} />}
          </Field>
          <Field label="End Date" required error={errors.end_date?.message}>
            {(p) => <Input {...p} type="date" readOnly={readOnly} {...register("end_date", { required: "Choose the last day.", validate: (v) => !watch("start_date") || v >= watch("start_date") || "Must not be before the start date." })} />}
          </Field>
          <Field label="Timezone" required help="All event-local dates and first entries use it." error={errors.timezone?.message}>
            {(p) => (
              <Select {...p} disabled={readOnly} {...register("timezone", { required: "Choose a timezone." })}>
                <option value="">Choose a timezone</option>
                {TIMEZONES.map((t) => <option key={t} value={t}>{t}</option>)}
              </Select>
            )}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Venue">
        <FieldGrid>
          <Field label="Venue">
            {(p) => (
              <Select {...p} disabled={readOnly} {...register("venue_id")}>
                <option value="">Not set</option>
                {(venues.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name}{v.city ? `, ${v.city}` : ""}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Country">
            {(p) => (
              <Select {...p} disabled={readOnly} {...register("country")}>
                <option value="">Not set</option>
                {COUNTRIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </Select>
            )}
          </Field>
          <Field label="City">{(p) => <Input {...p} readOnly={readOnly} {...register("city")} />}</Field>
          <Field label="Default Currency" required help="ISO code, e.g. IDR." error={errors.default_currency?.message}>
            {(p) => <Input {...p} className="uppercase" maxLength={3} readOnly={readOnly} {...register("default_currency", { required: "Enter a currency.", pattern: { value: /^[A-Za-z]{3}$/, message: "Use a 3-letter code." } })} />}
          </Field>
        </FieldGrid>
      </Section>
      <Section title="Registration and email">
        <FieldGrid>
          <Field label="Email Sender Name" help="Shown as the sender of QR emails.">
            {(p) => <Input {...p} readOnly={readOnly} {...register("email_sender_name")} />}
          </Field>
          <Field label="Reply-To Email" error={errors.email_reply_to?.message}>
            {(p) => <Input {...p} type="email" readOnly={readOnly} {...register("email_reply_to")} />}
          </Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] text-label">Website registration</span>
            <label className="flex h-8 items-center gap-2 text-[14px]">
              <Checkbox checked={watch("public_registration_open")} disabled={readOnly} onCheckedChange={(c) => setValue("public_registration_open", c === true, { shouldDirty: true })} />
              Open while the edition is Active
            </label>
          </div>
          <Field label="Scanner Cache Lifetime (minutes)" help="Empty uses the system default (12 hours)." error={errors.scanner_cache_ttl_minutes?.message}>
            {(p) => <Input {...p} type="number" min={5} max={10080} readOnly={readOnly} {...register("scanner_cache_ttl_minutes")} />}
          </Field>
        </FieldGrid>
      </Section>
    </>
  );
}
