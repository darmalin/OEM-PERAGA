import { COUNTRY_CODES } from "@ems/ui/countries";

// ISO 3166-1 alpha-2; names come from the browser in English (system language is English).
const CODES = COUNTRY_CODES;

const names = new Intl.DisplayNames(["en"], { type: "region" });

export const COUNTRIES = CODES.map((code) => ({ value: code, label: names.of(code) ?? code })).sort((a, b) =>
  a.label.localeCompare(b.label),
);

export function countryName(code: string | null | undefined): string {
  if (!code) return "";
  return names.of(code) ?? code;
}
