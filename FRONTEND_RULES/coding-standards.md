# Frontend Coding Standards

## TypeScript
- `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`.
- No `any`. Use `unknown` and narrow. `// @ts-expect-error` needs a reason.
- API data types are imported from `@ems/api`, never redeclared.

## Naming
- English only. Components `PascalCase`, hooks `useCamelCase`, files `kebab-case.tsx`, constants `UPPER_SNAKE`.
- Enum values from the API stay as the backend strings (`RETRY_NO_ANSWER`). Display text lives in `labels.ts` (`RETRY_NO_ANSWER: 'Retry No Answer'`). Never render raw enum strings.
- Field labels match the reference screenshot exactly (`First Name`, `Product Categories Interested In`, `Type of Buyers`). Changing a label needs owner approval (spec §4.1).

## React
- Function components only. Keep components under ~200 lines; split by section.
- Derive values instead of syncing state with `useEffect`. `useEffect` is for subscriptions and imperative APIs, not data fetching (TanStack Query does that).
- Lists use stable keys (`id`), never array index for data rows.
- Heavy lists (lead table) use TanStack Table with server-side pagination; virtualize only if page size > 100.

## Forms (React Hook Form + Zod)
- One Zod schema per form in `schemas.ts`, mirroring backend rules for fast feedback only. The backend remains the source of truth.
- Map API 422/409 `fields` into `setError` per field, plus a form-level message for `code`.
- Email/Phone: validate as a group ("Email or phone is required"), not two separate required fields.
- Valid Lead / Invalid: a single radio group with Undecided; never two checkboxes that can both be on.
- Send `version` with every update; on `VERSION_CONFLICT` show the conflict state from DESIGN.md and keep the user's values.
- `Ctrl/Cmd+S` submits the open form. Warn before leaving a dirty form.
- Disable the submit button while saving; never allow double submit.

## Styling
- Tailwind with the CSS variable tokens from `DESIGN/DESIGN.md`. No hard-coded hex colors in components; use tokens (`bg-input`, `text-label`).
- No arbitrary values (`mt-[13px]`) unless the spacing scale truly lacks it; add a comment why.
- Dark mode via `data-theme` / `.dark` class on `<html>`, driven by tokens. No per-component dark overrides with raw colors.

## Accessibility
- Every input has a `<label>` (visually as in the design). Errors linked with `aria-describedby`.
- Icon-only buttons have `aria-label`.
- Status indicators include the text, not just the dot color.
- Use Radix primitives (via shadcn) for dialogs, menus, popovers, selects; do not build them from `div`s.

## Copy
- Sentence case. Button text names the action ("Log Call", "Resend QR Email"). No "Submit", "Get Started", "Learn More".
- No emoji, no em dashes in UI strings.

## Quality gates
- `eslint` (with `jsx-a11y`, `react-hooks`), `tsc --noEmit`, `vitest`, and `prettier --check` pass in CI.
