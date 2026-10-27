import { countryOptions } from "@ems/ui/countries";
import { type FormEvent, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";

import { type Form, FormError, loadForm, submitForm, tokenFromPath } from "./api";
import { formatDate, initialLang, type Lang, saveLang, strings, type Strings } from "./i18n";
import { loadGtm, readUtm, track } from "./tracking";

type Field = Form["custom_fields"][number];
type Values = Record<string, string>;
type CustomValue = string | string[] | boolean;
type State = { kind: "loading" } | { kind: "closed" } | { kind: "error" } | { kind: "form"; form: Form } | { kind: "done"; form: Form };

const input =
  "h-10 w-full rounded-[8px] bg-input px-3 text-[15px] text-ink placeholder:text-label hover:bg-hover aria-[invalid=true]:ring-1 aria-[invalid=true]:ring-required";

export function App() {
  const token = useMemo(() => tokenFromPath(location.pathname), []);
  const utm = useMemo(() => readUtm(location.search), []);
  const [lang, setLang] = useState<Lang>(initialLang);
  const [state, setState] = useState<State>(token ? { kind: "loading" } : { kind: "closed" });
  const t = strings(lang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    if (!token) return;
    let gone = false;
    loadForm(token)
      .then((form) => {
        if (gone) return;
        setState({ kind: "form", form });
        loadGtm(form.gtm_container_id);
        track("campaign_form_view", { edition: form.edition.name, language: initialLang() });
      })
      .catch((e: unknown) => {
        if (!gone) setState(e instanceof FormError && e.status === 404 ? { kind: "closed" } : { kind: "error" });
      });
    return () => {
      gone = true;
    };
  }, [token]);

  const switchLang = () => {
    const next = lang === "en" ? "id" : "en";
    setLang(next);
    saveLang(next);
  };

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[560px] flex-col gap-5 px-4 py-6 sm:py-10">
      <div className="flex justify-end">
        <button type="button" onClick={switchLang} aria-label={t.switchLabel} className="h-9 rounded-[8px] px-3 text-[13px] text-link hover:bg-hover">
          {t.switchTo}
        </button>
      </div>
      {state.kind === "loading" ? (
        <p role="status" className="text-center text-label">{t.loading}</p>
      ) : state.kind === "closed" ? (
        <Card title={t.closedTitle}><p className="text-muted">{t.closed}</p></Card>
      ) : state.kind === "error" ? (
        <Card title={t.closedTitle}><p className="text-muted">{t.failed}</p></Card>
      ) : (
        <>
          <EventHeader form={state.form} lang={lang} t={t} />
          {state.kind === "done" ? (
            <Card title={t.doneTitle}><p role="status" className="text-muted">{t.done}</p></Card>
          ) : (
            <RegistrationForm
              token={token!}
              form={state.form}
              lang={lang}
              t={t}
              utm={utm}
              onDone={() => setState({ kind: "done", form: state.form })}
              onClosed={() => setState({ kind: "closed" })}
            />
          )}
        </>
      )}
    </main>
  );
}

function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-[12px] border border-line bg-bg p-5 sm:p-6">
      {title ? <h1 className="text-[20px] font-semibold">{title}</h1> : null}
      {children}
    </section>
  );
}

function EventHeader({ form, lang, t }: { form: Form; lang: Lang; t: Strings }) {
  const e = form.edition;
  const where = [e.venue_name, e.city].filter(Boolean).join(", ");
  return (
    <header className="flex flex-col gap-1 rounded-[12px] bg-band p-5 text-on-band sm:p-6">
      <p className="text-[13px] text-on-band-muted">{t.title}</p>
      <h1 className="text-[22px] leading-tight font-semibold">{e.name}</h1>
      <p className="text-[14px] text-on-band-muted">
        {t.dates(formatDate(e.start_date, lang), formatDate(e.end_date, lang))}
        {where ? ` · ${where}` : ""}
      </p>
    </header>
  );
}

function RegistrationForm({
  token,
  form,
  lang,
  t,
  utm,
  onDone,
  onClosed,
}: {
  token: string;
  form: Form;
  lang: Lang;
  t: Strings;
  utm: ReturnType<typeof readUtm>;
  onDone: () => void;
  onClosed: () => void;
}) {
  const [values, setValues] = useState<Values>({});
  const [custom, setCustom] = useState<Record<string, CustomValue>>({});
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(false);
  const countries = useMemo(() => countryOptions(lang), [lang]);

  const start = () => {
    if (started.current) return;
    started.current = true;
    track("campaign_form_start", { edition: form.edition.name, language: lang });
  };
  const set = (key: string, value: string) => {
    start();
    setValues((v) => ({ ...v, [key]: value }));
  };
  const setCustomValue = (key: string, value: CustomValue) => {
    start();
    setCustom((v) => ({ ...v, [key]: value }));
  };

  const check = (): Record<string, string> => {
    const out: Record<string, string> = {};
    if (!values.first_name?.trim()) out.first_name = t.required;
    if (!values.email?.trim() && !values.phone?.trim()) out.email = out.phone = t.needContact;
    for (const f of form.custom_fields) {
      const v = custom[f.key];
      const empty = v === undefined || v === "" || v === false || (Array.isArray(v) && v.length === 0);
      if (f.required && empty) out[`custom_fields.${f.key}`] = t.required;
    }
    if (!consent) out.consent = t.needConsent;
    return out;
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBanner(null);
    const found = check();
    setErrors(found);
    if (Object.keys(found).length) {
      setBanner(t.fixErrors);
      return;
    }
    setBusy(true);
    const text = (k: string) => values[k]?.trim() || null;
    const customFields = Object.fromEntries(
      Object.entries(custom).filter(([, v]) => v !== "" && v !== false && !(Array.isArray(v) && v.length === 0)),
    );
    try {
      await submitForm(token, {
        first_name: values.first_name!.trim(),
        email: text("email"),
        phone: text("phone"),
        company_name: text("company_name"),
        job_title: text("job_title"),
        country: text("country"),
        city: text("city"),
        custom_fields: customFields,
        consent: true,
        ticket: form.ticket,
        contact_fax: values.contact_fax || null,
        ...utm,
      });
      track("campaign_form_submit", { edition: form.edition.name, language: lang });
      onDone();
    } catch (err) {
      if (err instanceof FormError && err.status === 404) onClosed();
      else if (err instanceof FormError && err.status === 422 && Object.keys(err.fields).length) {
        setErrors(serverErrors(err.fields, t));
        setBanner(t.fixErrors);
      } else setBanner(err instanceof FormError && err.status === 429 ? t.tooMany : t.failed);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <p className="text-muted">{t.intro}</p>
      <form onSubmit={(e) => void submit(e)} noValidate className="flex flex-col gap-4">
        {banner ? <p role="alert" className="rounded-[8px] bg-[var(--red-bg)] px-3 py-2 text-[13px] text-[var(--red-fg)]">{banner}</p> : null}
        <TextField label={t.firstName} required name="first_name" autoComplete="name" values={values} errors={errors} onChange={set} t={t} />
        <TextField label={t.email} name="email" type="email" autoComplete="email" hint={t.contactHint} values={values} errors={errors} onChange={set} t={t} />
        <TextField label={t.phone} name="phone" type="tel" autoComplete="tel" values={values} errors={errors} onChange={set} t={t} />
        <TextField label={t.company} name="company_name" autoComplete="organization" values={values} errors={errors} onChange={set} t={t} />
        <TextField label={t.jobTitle} name="job_title" autoComplete="organization-title" values={values} errors={errors} onChange={set} t={t} />
        <Labeled label={t.country} optional={t.optional} error={errors.country}>
          {(p) => (
            <select {...p} className={`${input} cursor-pointer`} value={values.country ?? ""} autoComplete="country" onChange={(e) => set("country", e.target.value)}>
              <option value="">{t.chooseCountry}</option>
              {countries.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          )}
        </Labeled>
        <TextField label={t.city} name="city" autoComplete="address-level2" values={values} errors={errors} onChange={set} t={t} />
        {form.custom_fields.map((f) => (
          <CustomInput key={f.key} field={f} value={custom[f.key]} error={errors[`custom_fields.${f.key}`]} onChange={(v) => setCustomValue(f.key, v)} t={t} />
        ))}
        {/* Honeypot: hidden from people and screen readers; bots fill every field. */}
        <div aria-hidden className="absolute -left-[9999px] h-px w-px overflow-hidden">
          <label>
            Fax
            <input tabIndex={-1} autoComplete="off" value={values.contact_fax ?? ""} onChange={(e) => setValues((v) => ({ ...v, contact_fax: e.target.value }))} />
          </label>
        </div>
        <div className="flex flex-col gap-1">
          <label className="flex items-start gap-3 text-[14px] leading-snug">
            <input
              type="checkbox"
              className="mt-0.5 size-5 shrink-0 accent-[var(--primary)]"
              checked={consent}
              aria-invalid={Boolean(errors.consent)}
              aria-describedby={errors.consent ? "consent-error" : undefined}
              onChange={(e) => {
                start();
                setConsent(e.target.checked);
              }}
            />
            <span>{t.consent}</span>
          </label>
          {errors.consent ? <p id="consent-error" className="pl-8 text-[13px] text-required">{errors.consent}</p> : null}
        </div>
        <button type="submit" disabled={busy} className="h-11 rounded-[8px] bg-primary text-[15px] font-medium text-on-primary hover:opacity-90 disabled:opacity-60">
          {busy ? t.sending : t.submit}
        </button>
      </form>
    </Card>
  );
}

/** Server messages are in English; map the common ones to the form's language. */
function serverErrors(fields: Record<string, string>, t: Strings): Record<string, string> {
  return Object.fromEntries(
    Object.entries(fields).map(([k, v]) => [k, /required/i.test(v) ? t.required : v]),
  );
}

function Labeled({
  label,
  required,
  optional,
  hint,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  optional?: string;
  hint?: string;
  error?: string;
  children: (p: { id: string; "aria-invalid": boolean; "aria-describedby"?: string; "aria-required"?: boolean }) => ReactNode;
}) {
  const id = useId();
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[14px] font-medium">
        {label}
        {required ? <span className="text-required" aria-hidden> *</span> : optional ? <span className="font-normal text-label"> ({optional})</span> : null}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describedBy, "aria-required": required || undefined })}
      {error ? <p id={`${id}-error`} className="text-[13px] text-required">{error}</p> : hint ? <p id={`${id}-hint`} className="text-[13px] text-label">{hint}</p> : null}
    </div>
  );
}

function TextField({
  label,
  name,
  required,
  type = "text",
  autoComplete,
  hint,
  values,
  errors,
  onChange,
  t,
}: {
  label: string;
  name: string;
  required?: boolean;
  type?: string;
  autoComplete?: string;
  hint?: string;
  values: Values;
  errors: Record<string, string>;
  onChange: (key: string, value: string) => void;
  t: Strings;
}) {
  return (
    <Labeled label={label} required={required} optional={required || name === "email" || name === "phone" ? undefined : t.optional} hint={hint} error={errors[name]}>
      {(p) => <input {...p} name={name} type={type} autoComplete={autoComplete} maxLength={name === "email" ? 320 : 200} className={input} value={values[name] ?? ""} onChange={(e) => onChange(name, e.target.value)} />}
    </Labeled>
  );
}

function CustomInput({ field: f, value, error, onChange, t }: { field: Field; value: CustomValue | undefined; error?: string; onChange: (v: CustomValue) => void; t: Strings }) {
  if (f.type === "checkbox") {
    return (
      <div className="flex flex-col gap-1">
        <label className="flex items-center gap-3 text-[14px]">
          <input type="checkbox" className="size-5 accent-[var(--primary)]" checked={value === true} onChange={(e) => onChange(e.target.checked)} />
          <span>{f.label}{f.required ? <span className="text-required" aria-hidden> *</span> : null}</span>
        </label>
        {error ? <p className="pl-8 text-[13px] text-required">{error}</p> : null}
      </div>
    );
  }
  if (f.type === "multi_select") {
    const picked = Array.isArray(value) ? value : [];
    return (
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-[14px] font-medium">
          {f.label}
          {f.required ? <span className="text-required" aria-hidden> *</span> : <span className="font-normal text-label"> ({t.optional})</span>}
        </legend>
        {f.options.map((o) => (
          <label key={o} className="flex items-center gap-3 text-[14px]">
            <input
              type="checkbox"
              className="size-5 accent-[var(--primary)]"
              checked={picked.includes(o)}
              onChange={(e) => onChange(e.target.checked ? [...picked, o] : picked.filter((x) => x !== o))}
            />
            {o}
          </label>
        ))}
        {error ? <p className="text-[13px] text-required">{error}</p> : null}
      </fieldset>
    );
  }
  const str = typeof value === "string" ? value : "";
  return (
    <Labeled label={f.label} required={f.required} optional={t.optional} error={error}>
      {(p) =>
        f.type === "select" ? (
          <select {...p} className={`${input} cursor-pointer`} value={str} onChange={(e) => onChange(e.target.value)}>
            <option value="">{t.choose}</option>
            {f.options.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        ) : f.type === "textarea" ? (
          <textarea {...p} className={`${input} h-24 py-2`} maxLength={2000} value={str} onChange={(e) => onChange(e.target.value)} />
        ) : (
          <input
            {...p}
            className={input}
            type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
            inputMode={f.type === "number" ? "decimal" : undefined}
            maxLength={f.type === "text" ? 500 : undefined}
            value={str}
            onChange={(e) => onChange(e.target.value)}
          />
        )
      }
    </Labeled>
  );
}
