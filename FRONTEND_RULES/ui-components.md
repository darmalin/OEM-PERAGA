# UI Components (shadcn restyled to Frappe Desk)

Visual source of truth: `DESIGN/DESIGN.md`. This file is how to implement it.

## Tokens
- Define every color from DESIGN.md as CSS variables in `packages/ui/src/styles/tokens.css`, light on `:root`, dark on `.dark`. Map them in Tailwind v4 `@theme`.
- Override shadcn's default variables (`--background`, `--foreground`, `--primary`, `--input`, `--ring`, `--radius`...) to these tokens. Do not keep shadcn's default zinc/slate look.
- Font: Inter variable, self-hosted in `packages/ui/src/fonts`, `font-feature-settings: "cv11"` optional, `tabular-nums` utility for IDs and numbers.

## shadcn component changes

| Component | Change from shadcn default |
|---|---|
| `Input`, `Textarea`, `Select` trigger | Filled `--surface-input`, no border, radius 8px, height 32px (44px on `pointer: coarse`). Hover `--surface-hover`. Focus: 2px `--focus` ring with 2px offset. |
| `Button` | Variants: `primary` (ink bg), `secondary` (`--surface-input` bg, ink text), `ghost`, `danger` (red text on subtle bg). Radius 8px. No arrows or icons by default. |
| `Checkbox`, `RadioGroup` | Radius 4px checkbox; ink fill when checked. |
| `Dialog`, `Popover`, `DropdownMenu`, `Command` | The only components with a shadow. Radius 12px (dialog), 8px (menus). |
| `Table` | Row lines only, 40px rows, hover `--surface-hover`, sticky header. |
| `Badge` | Replaced by `Indicator` for statuses; plain `Badge` only for counts (filter count). |
| `Tabs` | Underline style like the screenshot (`Person` tab), not pill segmented control. |
| `Toast` (sonner) | Bottom-right, neutral surface, status word + message. |

## Frappe patterns (build once in `packages/ui`)
- **`Indicator`**: `<Indicator status="RETRY_NO_ANSWER" />` renders dot + label with colors from `status.ts`. The only way statuses are shown.
- **`PageHead`**: title, indicators, secondary actions, one primary action.
- **`ListView`**: filter bar (search, standard filters, Filter popover, sort), table with selection, bulk action bar, footer with count and page size. Props: columns, query hook, filters schema.
- **`FormLayout`**: tabs, `FormSection` (collapsible, chevron, persisted open state), `FieldGrid` (3/2/1 columns), `Field` (label, required mark, help, error), right sidebar slot.
- **`ActivityTimeline`**: audit and activity entries with actor, action, relative time, expandable diff.
- **`CommandBar`**: `Ctrl/Cmd+K`, searches routes the user can open and records (leads by name, email, phone, Registration ID).
- **`EmptyState`**, **`ErrorState`**, **`NoAccess`**: one-sentence cause + one action.

## States checklist (per screen)
- Loading: skeleton matching the final layout.
- Empty first run and empty filtered are different messages.
- Error shows the message and `request_id`, with Retry.
- No permission shows NoAccess, never a broken page.
- Long values (company names, Vietnamese text, emails) wrap or truncate with a tooltip; never overflow the cell.

## Responsive
- Breakpoints: `< 768` (phone), `768 to 1023` (tablet), `1024 to 1279` (laptop), `>= 1280` (desktop).
- Form grid 1 / 2 / 3 / 3 columns; form sidebar moves below the form under 1280.
- List view on phones: card-like rows showing name, indicator, phone, owner (stacked), still one tap to open. No horizontal page scroll; the table itself may scroll horizontally inside its container on tablet.
- Sidebar becomes a drawer under 768.

## Icons
- `lucide-react`, size 16, stroke 1.5, imported per icon. Only for meaning (navigation, toolbar actions, chevrons). No decorative icons.

## Motion
- Popover/dialog open 120ms ease-out. Nothing else animates. Respect `prefers-reduced-motion`.

## Assets
- No logo until the owner provides one: render "EMS" as text. No avatars generated; user avatars are initials on `--surface-input`.
