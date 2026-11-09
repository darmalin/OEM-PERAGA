import { Plus, Trash2 } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import { Button, Field, Input, Textarea } from "../ui";

/** Answers as the API stores them (orders/details.py); paths like "own_contractor.email". */
export type Answers = Record<string, unknown>;
export type DetailsType =
  | "directory_listing" | "advertising" | "social_media" | "stand_service" | "exhibit_details" | "freight"
  | "badges_visa" | "seminar" | "parking";

export const DETAILS_TITLES: Record<DetailsType, string> = {
  directory_listing: "E-Directory Listing",
  advertising: "Advertising Details",
  social_media: "Social Media Promotion",
  stand_service: "Stand Service and Contractor",
  exhibit_details: "Exhibit Details",
  freight: "Freight Forwarder",
  badges_visa: "Badges and Visa",
  seminar: "Seminar",
  parking: "Parking Pass Holders",
};

/** Question order per set, for showing answers back in the order they were asked. */
const FIELD_ORDER: Record<DetailsType, string[]> = {
  directory_listing: ["agent_or_principal", "listed_as", "brief_introduction", "product_categories", "product_details", "agent_principal_listings", "looking_for_local_agent"],
  advertising: ["logo_shape", "image_url"],
  social_media: ["product_category", "product_description", "video_link", "video_title", "video_description", "facebook", "x", "linkedin", "instagram", "youtube"],
  stand_service: ["service", "contractor", "official_contractor", "own_contractor"],
  exhibit_details: ["items", "sale_and_operation", "purchased"],
  freight: ["uses_official", "official_forwarder", "non_official", "shipments"],
  badges_visa: ["company_type", "badges", "vip_needed", "vip_badges", "needs_visa_letter"],
  seminar: ["topic", "date", "time", "speakers"],
  parking: ["plates"],
};

const KEY_LABELS: Record<string, string> = {
  agent_or_principal: "You are", listed_as: "Listed as", brief_introduction: "Introduction", product_categories: "Categories",
  agent_principal_listings: "Agents or principals", looking_for_local_agent: "Looking for a local agent", x: "X (Twitter)",
  contractor: "Stand built by", official_contractor: "Official contractor", own_contractor: "Own contractor", items: "Exhibits",
  sale_and_operation: "The exhibits are", uses_official: "Official forwarder", official_forwarder: "Forwarder",
  non_official: "Own forwarder", company_type: "Company type", badges: "Exhibitor badges", vip_needed: "VIP badges",
  vip_badges: "VIP guests", needs_visa_letter: "Visa invitation letter", plates: "Plate numbers",
};

const VALUE_LABELS: Record<string, string> = {
  AGENT: "Agent", PRINCIPAL: "Principal", MANUFACTURER: "Manufacturer", DISTRIBUTOR_AGENT: "Distributor / Agent",
  LOOKING_FOR_DISTRIBUTOR: "Looking for a distributor", NONE: "None of the above", SQUARE: "Square", RECTANGLE: "Rectangle",
  OFFICIAL: "An official contractor", OWN: "Our own contractor", SALE_OPERATED: "For sale and operated",
  SALE_DISPLAY_ONLY: "For sale, display only", NOT_FOR_SALE_DISPLAY_ONLY: "Not for sale, display only",
  NOT_FOR_SALE_OPERATED: "Not for sale, operated", LOCAL: "Indonesian company", OVERSEAS: "Overseas company",
  MALE: "Male", FEMALE: "Female",
};

function plain(value: unknown): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "string") return VALUE_LABELS[value] ?? value;
  if (Array.isArray(value)) {
    return value.map((v) => (v && typeof v === "object" ? orderedKeys(Object.keys(v), COLUMN_ORDER).map((k) => plain((v as Answers)[k])).join(", ") : plain(v))).join("; ");
  }
  if (value && typeof value === "object") return Object.values(value as Answers).map(plain).join(", ");
  return String(value);
}

/** Answers back as label and plain words, in the order asked (review page). */
export function answerRows(type: DetailsType, answers: Answers): [string, string][] {
  const keys = orderedKeys(Object.keys(answers), FIELD_ORDER[type]);
  return keys.map((k) => [KEY_LABELS[k] ?? k.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase()), plain(answers[k])]);
}

const COLUMN_ORDER = ["quantity", "full_name", "name", "company", "description", "designation", "gender", "country", "title_of_speech", "dimension", "length_m", "width_m", "height_m", "weight_kg"];

function orderedKeys(keys: string[], order: string[]): string[] {
  return [...order.filter((k) => keys.includes(k)), ...keys.filter((k) => !order.includes(k))];
}

function get(obj: Answers, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Answers)[k] : undefined), obj);
}

function setIn(obj: Answers, path: string, value: unknown): Answers {
  const [head, ...rest] = path.split(".");
  if (!head) return obj;
  if (rest.length === 0) return { ...obj, [head]: value };
  const child = obj[head] && typeof obj[head] === "object" ? (obj[head] as Answers) : {};
  return { ...obj, [head]: setIn(child, rest.join("."), value) };
}

/** Drop blanks before saving: the API stores only what was answered. */
export function cleanAnswers(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(cleanAnswers).filter((v) => v !== undefined);
  }
  if (value && typeof value === "object") {
    const out: Answers = {};
    for (const [k, v] of Object.entries(value)) {
      const c = cleanAnswers(v);
      if (c !== undefined) out[k] = c;
    }
    return Object.keys(out).length ? out : undefined;
  }
  if (typeof value === "string") return value.trim() === "" ? undefined : value;
  return value ?? undefined;
}

interface Ctx {
  value: Answers;
  onChange: (next: Answers) => void;
  errors: Record<string, string>;
  disabled: boolean;
  options: Record<string, string[] | undefined>;
}

function error(ctx: Ctx, path: string): string | undefined {
  return ctx.errors[`details.${path}`];
}

function Text({ ctx, path, label, required, long, max = 200, help, type }: { ctx: Ctx; path: string; label: string; required?: boolean; long?: boolean; max?: number; help?: string; type?: string }) {
  const v = (get(ctx.value, path) as string | undefined) ?? "";
  const set = (s: string) => ctx.onChange(setIn(ctx.value, path, s));
  return (
    <Field label={label} required={required} help={help} error={error(ctx, path)} className={long ? "sm:col-span-2" : undefined}>
      {(p) => long
        ? <Textarea {...p} value={v} maxLength={max} disabled={ctx.disabled} onChange={(e) => set(e.target.value)} />
        : <Input {...p} type={type ?? "text"} value={v} maxLength={max} disabled={ctx.disabled} onChange={(e) => set(e.target.value)} />}
    </Field>
  );
}

function Choice({ ctx, path, label, choices, required }: { ctx: Ctx; path: string; label: string; choices: [string, string][]; required?: boolean }) {
  const v = get(ctx.value, path) as string | undefined;
  const err = error(ctx, path);
  return (
    <fieldset className="flex flex-col gap-2 sm:col-span-2" aria-invalid={Boolean(err)}>
      <legend className="mb-1.5 text-[14px] font-medium text-ink">{label}{required ? <span className="ml-0.5 text-required" aria-hidden> *</span> : null}</legend>
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {choices.map(([value, text]) => (
          <label key={value} className="flex items-center gap-2 text-[14px]">
            <input type="radio" className="size-4 accent-[var(--primary)]" name={path} checked={v === value} disabled={ctx.disabled} onChange={() => ctx.onChange(setIn(ctx.value, path, value))} />
            {text}
          </label>
        ))}
      </div>
      {err ? <p className="text-[12px] text-required">{err}</p> : null}
    </fieldset>
  );
}

function Pick({ ctx, path, label, kind, required, empty }: { ctx: Ctx; path: string; label: string; kind: string; required?: boolean; empty: string }) {
  const choices = ctx.options[kind] ?? [];
  if (choices.length === 0) {
    return <p className="text-[13px] text-label sm:col-span-2">{label}: {empty}</p>;
  }
  return <Choice ctx={ctx} path={path} label={label} required={required} choices={choices.map((c) => [c, c])} />;
}

function YesNo({ ctx, path, label }: { ctx: Ctx; path: string; label: string }) {
  const v = get(ctx.value, path) as boolean | undefined;
  return (
    <Choice ctx={{ ...ctx, value: { [path]: v === undefined ? undefined : v ? "yes" : "no" }, onChange: (n) => ctx.onChange(setIn(ctx.value, path, n[path] === "yes")) }} path={path} label={label} choices={[["yes", "Yes"], ["no", "No"]]} />
  );
}

function Multi({ ctx, path, label, kind, required }: { ctx: Ctx; path: string; label: string; kind: string; required?: boolean }) {
  const chosen = (get(ctx.value, path) as string[] | undefined) ?? [];
  const choices = ctx.options[kind] ?? [];
  const err = error(ctx, path) ?? Object.entries(ctx.errors).find(([k]) => k.startsWith(`details.${path}.`))?.[1];
  return (
    <fieldset className="flex flex-col gap-2 sm:col-span-2">
      <legend className="mb-1.5 text-[14px] font-medium text-ink">{label}{required ? <span className="ml-0.5 text-required" aria-hidden> *</span> : null}</legend>
      {choices.length === 0 ? <p className="text-[13px] text-label">The organizer has not listed the categories yet.</p> : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {choices.map((c) => (
            <label key={c} className="flex items-center gap-2 text-[14px]">
              <input type="checkbox" className="size-4 accent-[var(--primary)]" checked={chosen.includes(c)} disabled={ctx.disabled}
                onChange={(e) => ctx.onChange(setIn(ctx.value, path, e.target.checked ? [...chosen, c] : chosen.filter((x) => x !== c)))} />
              {c}
            </label>
          ))}
        </div>
      )}
      {err ? <p className="text-[12px] text-required">{err}</p> : null}
    </fieldset>
  );
}

interface Column {
  key: string;
  label: string;
  kind?: "text" | "number" | "gender";
  width?: string;
}

function Rows({ ctx, path, label, columns, max, add, required }: { ctx: Ctx; path: string; label: string; columns: Column[]; max: number; add: string; required?: boolean }) {
  const rows = (get(ctx.value, path) as Answers[] | undefined) ?? [];
  const setRows = (next: Answers[]) => ctx.onChange(setIn(ctx.value, path, next));
  const err = error(ctx, path);
  return (
    <div className="flex flex-col gap-2 sm:col-span-2">
      <div className="mb-1.5 text-[14px] font-medium text-ink">{label}{required ? <span className="ml-0.5 text-required" aria-hidden> *</span> : null}</div>
      {rows.map((row, n) => (
        <div key={n} className="grid grid-cols-1 gap-2 rounded-[12px] border border-line bg-page/60 p-4 sm:grid-cols-[repeat(var(--cols),minmax(0,1fr))_auto]" style={{ "--cols": columns.length } as CSSProperties}>
          {columns.map((c) => {
            const cellPath = `${path}.${n}.${c.key}`;
            const v = row[c.key];
            const set = (value: unknown) => setRows(rows.map((r, i) => (i === n ? { ...r, [c.key]: value } : r)));
            return (
              <Field key={c.key} label={`${c.label} ${n + 1}`} error={error(ctx, cellPath)}>
                {(p) => c.kind === "gender" ? (
                  <select {...p} className="h-11 rounded-[10px] border border-line-strong bg-bg px-3 text-[15px]" value={(v as string | undefined) ?? ""} disabled={ctx.disabled} onChange={(e) => set(e.target.value || undefined)}>
                    <option value="">Not set</option><option value="MALE">Male</option><option value="FEMALE">Female</option>
                  </select>
                ) : (
                  <Input {...p} inputMode={c.kind === "number" ? "decimal" : undefined} value={v == null ? "" : String(v)} disabled={ctx.disabled}
                    onChange={(e) => set(c.kind === "number" ? (e.target.value.trim() === "" ? undefined : Number(e.target.value.replace(",", "."))) : e.target.value)} />
                )}
              </Field>
            );
          })}
          {ctx.disabled ? null : (
            <div className="flex items-end"><Button type="button" variant="ghost" className="h-10" aria-label={`Remove row ${n + 1} of ${label}`} onClick={() => setRows(rows.filter((_, i) => i !== n))}><Trash2 aria-hidden /></Button></div>
          )}
        </div>
      ))}
      {err ? <p className="text-[12px] text-required">{err}</p> : null}
      {ctx.disabled || rows.length >= max ? null : (
        <div><Button type="button" variant="ghost" className="h-9" onClick={() => setRows([...rows, {}])}><Plus aria-hidden />{add}</Button></div>
      )}
    </div>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 gap-x-5 gap-y-4 sm:grid-cols-2">{children}</div>;
}

/** The question set of a form. Choices come from the organizer (order form options). */
export function Questions({ type, ...ctx }: { type: DetailsType } & Ctx) {
  switch (type) {
    case "directory_listing":
      return (
        <Grid>
          <Choice ctx={ctx} path="agent_or_principal" label="You are" required choices={[["PRINCIPAL", "Principal"], ["AGENT", "Agent"]]} />
          <Choice ctx={ctx} path="listed_as" label="List us as" required choices={[["MANUFACTURER", "Manufacturer"], ["DISTRIBUTOR_AGENT", "Distributor / Agent"], ["LOOKING_FOR_DISTRIBUTOR", "Looking for a distributor"], ["NONE", "None of the above"]]} />
          <Text ctx={ctx} path="brief_introduction" label="Brief introduction to your exhibits and products" required long max={2000} />
          <Multi ctx={ctx} path="product_categories" label="Product categories" kind="PRODUCT_CATEGORY" required />
          <Text ctx={ctx} path="product_details" label="Product details" long max={2000} />
          <Rows ctx={ctx} path="agent_principal_listings" label="Agents or principals to list" max={20} add="Add Company" columns={[{ key: "company", label: "Company" }, { key: "country", label: "Country" }]} />
          <YesNo ctx={ctx} path="looking_for_local_agent" label="Are you looking for a local agent in Indonesia?" />
        </Grid>
      );
    case "advertising":
      return (
        <Grid>
          <Choice ctx={ctx} path="logo_shape" label="Logo shape" choices={[["SQUARE", "Square"], ["RECTANGLE", "Rectangle"]]} />
          <Text ctx={ctx} path="image_url" label="Link to your advertisement image" type="url" max={500} help="Or attach the file below." />
        </Grid>
      );
    case "social_media":
      return (
        <Grid>
          <Pick ctx={ctx} path="product_category" label="Product category" kind="PRODUCT_CATEGORY" required empty="the organizer has not listed the categories yet." />
          <Text ctx={ctx} path="product_description" label="Product description" long max={800} help="Up to 800 characters." />
          <Text ctx={ctx} path="video_link" label="Video link" type="url" max={500} />
          <Text ctx={ctx} path="video_title" label="Video title" />
          <Text ctx={ctx} path="video_description" label="Video description" long max={800} />
          {(["facebook", "x", "linkedin", "instagram", "youtube"] as const).map((k) => (
            <Text key={k} ctx={ctx} path={k} label={{ facebook: "Facebook", x: "X (Twitter)", linkedin: "LinkedIn", instagram: "Instagram", youtube: "YouTube" }[k]} type="url" max={500} />
          ))}
        </Grid>
      );
    case "stand_service": {
      const contractor = get(ctx.value, "contractor");
      return (
        <Grid>
          <Pick ctx={ctx} path="service" label="Stand service" kind="STAND_SERVICE" required empty="the organizer has not listed the services yet." />
          <Choice ctx={ctx} path="contractor" label="Who builds your stand?" required choices={[["OFFICIAL", "An official contractor"], ["OWN", "Our own contractor"]]} />
          {contractor === "OFFICIAL" ? <Pick ctx={ctx} path="official_contractor" label="Official contractor" kind="OFFICIAL_CONTRACTOR" required empty="the organizer has not listed them yet." /> : null}
          {contractor === "OWN" ? (
            <>
              <Text ctx={ctx} path="own_contractor.name" label="Contractor name" required />
              <Text ctx={ctx} path="own_contractor.pic" label="Person in charge" required />
              <Text ctx={ctx} path="own_contractor.mobile" label="Mobile" required max={50} />
              <Text ctx={ctx} path="own_contractor.email" label="Email" required type="email" max={320} />
              <Text ctx={ctx} path="own_contractor.address" label="Address and country" long max={2000} />
            </>
          ) : null}
        </Grid>
      );
    }
    case "exhibit_details":
      return (
        <Grid>
          <Rows ctx={ctx} path="items" label="Exhibits" required max={50} add="Add Exhibit" columns={[{ key: "quantity", label: "Quantity", kind: "number" }, { key: "description", label: "Description" }, { key: "dimension", label: "Dimension" }, { key: "weight_kg", label: "Weight (kg)", kind: "number" }]} />
          <Choice ctx={ctx} path="sale_and_operation" label="The exhibits are" required choices={[["SALE_OPERATED", "For sale and operated"], ["SALE_DISPLAY_ONLY", "For sale, display only"], ["NOT_FOR_SALE_DISPLAY_ONLY", "Not for sale, display only"], ["NOT_FOR_SALE_OPERATED", "Not for sale, operated"]]} />
          <YesNo ctx={ctx} path="purchased" label="Have the exhibits been purchased?" />
        </Grid>
      );
    case "freight": {
      const official = get(ctx.value, "uses_official");
      return (
        <Grid>
          <YesNo ctx={ctx} path="uses_official" label="Will you use an official freight forwarder?" />
          {official === true ? <Pick ctx={ctx} path="official_forwarder" label="Official freight forwarder" kind="OFFICIAL_FORWARDER" required empty="the organizer has not listed them yet." /> : null}
          {official === false ? (
            <>
              <Text ctx={ctx} path="non_official.company" label="Forwarder company" required />
              <Text ctx={ctx} path="non_official.agent" label="Agent" />
              <Text ctx={ctx} path="non_official.country" label="Country of origin" required />
              <Text ctx={ctx} path="non_official.city" label="City" />
              <Text ctx={ctx} path="non_official.phone" label="Phone" required max={50} />
              <Text ctx={ctx} path="non_official.email" label="Email" required type="email" max={320} />
              <Text ctx={ctx} path="non_official.authorized_person" label="Authorized person" required />
              <Text ctx={ctx} path="non_official.designation" label="Designation" />
              <Text ctx={ctx} path="non_official.address" label="Address" long max={2000} />
            </>
          ) : null}
          <Rows ctx={ctx} path="shipments" label="Shipment" max={50} add="Add Package" columns={[{ key: "quantity", label: "Quantity", kind: "number" }, { key: "description", label: "Contents" }, { key: "length_m", label: "L (m)", kind: "number" }, { key: "width_m", label: "W (m)", kind: "number" }, { key: "height_m", label: "H (m)", kind: "number" }, { key: "weight_kg", label: "Weight (kg)", kind: "number" }]} />
        </Grid>
      );
    }
    case "badges_visa":
      return (
        <Grid>
          <Choice ctx={ctx} path="company_type" label="Company type" required choices={[["LOCAL", "Indonesian company"], ["OVERSEAS", "Overseas company"]]} />
          <Rows ctx={ctx} path="badges" label="Exhibitor badges" required max={50} add="Add Badge" columns={[{ key: "full_name", label: "Full name" }, { key: "gender", label: "Gender", kind: "gender" }, { key: "designation", label: "Designation" }]} />
          <YesNo ctx={ctx} path="vip_needed" label="Do you need VIP badges for special guests?" />
          {get(ctx.value, "vip_needed") === true ? (
            <Rows ctx={ctx} path="vip_badges" label="VIP guests" required max={20} add="Add VIP Guest" columns={[{ key: "full_name", label: "Full name" }, { key: "designation", label: "Designation" }, { key: "company", label: "Company" }]} />
          ) : null}
          <YesNo ctx={ctx} path="needs_visa_letter" label="Do you need an invitation letter for a visa?" />
        </Grid>
      );
    case "seminar":
      return (
        <Grid>
          <Text ctx={ctx} path="topic" label="Seminar topic" required max={300} />
          <Pick ctx={ctx} path="date" label="Date" kind="SEMINAR_DATE" required empty="the organizer has not set the dates yet." />
          <Text ctx={ctx} path="time" label="Preferred time" max={50} />
          <Rows ctx={ctx} path="speakers" label="Speakers" required max={3} add="Add Speaker" columns={[{ key: "name", label: "Name" }, { key: "designation", label: "Designation" }, { key: "company", label: "Company" }, { key: "title_of_speech", label: "Title of speech" }]} />
        </Grid>
      );
    case "parking": {
      const plates = (get(ctx.value, "plates") as string[] | undefined) ?? [];
      return (
        <Grid>
          <Rows
            ctx={{ ...ctx, value: { plates: plates.map((p) => ({ plate: p })) }, onChange: (n) => ctx.onChange(setIn(ctx.value, "plates", ((n.plates as Answers[] | undefined) ?? []).map((r) => (r.plate as string | undefined) ?? ""))) }}
            path="plates" label="Plate numbers" required max={50} add="Add Plate" columns={[{ key: "plate", label: "Plate number" }]}
          />
        </Grid>
      );
    }
  }
}
