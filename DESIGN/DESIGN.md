# DESIGN.md: EMS Visitor CRM

Design direction for the web app (desk) and the gate scanner PWA. Built on shadcn/ui + Tailwind, restyled to look and behave like Frappe Desk / ERPNext v15, as requested by the product owner.

Filter: antislop (during). Direction source: product owner asked for a Frappe/ERPNext look; the team are Frappe engineers and the current tool is Frappe (see `DEV_DOCS/WhatsApp Image ... .jpeg`). R-30 (no clones) is waived by that explicit request. Record: *owner asked for the ERPNext look; kept*.

## Design Read

> Reading this as: an internal data-entry CRM for telemarketing agents, managers and gate staff, in a Frappe Desk / ERPNext v15 visual language, dial **ENERGY 1 / RHYTHM 1 / MOTION 1**.

- ENERGY 1: agents sit in this tool for full shifts. The screen should never compete with the data.
- RHYTHM 1: uniform on purpose. List, form, list, form. Predictability is what makes a desk app fast; a lead form must look like every other form.
- MOTION 1: hover, focus, and open/close of popovers and dialogs only. No scroll reveals, no loops.

## Identity

| Trait | Means in practice |
|---|---|
| Familiar | A Frappe user should know where everything is without training: sidebar, list, form, Activity at the bottom. |
| Dense, calm | Many fields per screen, small type, filled grey inputs, almost no borders. |
| Honest state | Every status is a colored indicator with a word. Color is never the only signal. |
| Fast by keyboard | Command bar, `Ctrl+S` save, `Ctrl+K` search, list navigation with arrow keys. |

**Identity motif:** the Frappe indicator pill (dot + word on a tinted background) for every status in the system: telemarketing status, Attend, registration, QR, scan result, import job. Same shape everywhere, so status reads at a glance. A second motif is the collapsible section header with a chevron (`Person ⌄`, `Verification ⌄`), taken from the reference screenshot.

**One deliberate accent:** the primary action button in ink black (Frappe v15 style). Blue is reserved for links and the focus ring. Nothing else is colored except status indicators.

## Color

Neutral base + ink + one blue for links/focus. Status colors are semantic, used only inside indicators and scanner result screens. All pairs below were checked for WCAG AA.

### Light

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | Page and form surface |
| `--bg-subtle` | `#F8F8F8` | Sidebar, page background behind cards |
| `--surface-input` | `#F3F3F3` | Filled inputs (no border, as in screenshot) |
| `--surface-hover` | `#EDEDED` | Row hover, input hover |
| `--border` | `#E2E2E2` | Section dividers, table row lines, card outline |
| `--ink` | `#171717` | Body text, values, primary button background |
| `--ink-muted` | `#525252` | Secondary text, gray indicator text |
| `--ink-label` | `#6B6B6B` | Field labels, placeholders, timestamps (5.33:1 on white, 4.8:1 on input) |
| `--ink-on-primary` | `#FFFFFF` | Text on primary button |
| `--link` | `#0B6BCB` | Links (5.28:1) |
| `--focus` | `#0B6BCB` | 2px focus ring, 2px offset |
| `--required` | `#C4302B` | Required asterisk, field error text (5.52:1) |

### Dark

| Token | Value |
|---|---|
| `--bg` | `#171717` |
| `--bg-subtle` | `#1F1F1F` |
| `--surface-input` | `#2A2A2A` |
| `--surface-hover` | `#333333` |
| `--border` | `#333333` |
| `--ink` | `#EDEDED` (12.26:1 on input) |
| `--ink-muted` | `#C7C7C7` |
| `--ink-label` | `#A3A3A3` on `#1F1F1F` (6.53:1), placeholders `#9A9A9A` on input (5.1:1) |
| primary button | `#EDEDED` background, `#171717` text |
| `--link` / `--focus` | `#5AA9F5` (7.2:1) |
| `--required` | `#F58A80` |

Theme: Light, Dark, and System, switchable from the user menu. Reason: Frappe offers the same choice, and agents work long shifts in different lighting; both modes are shipped and tested (R-21, R-34).

### Status indicators

| Indicator | Light text / bg | Dark text / bg | Used for |
|---|---|---|---|
| Gray | `#525252` / `#F3F3F3` | `#C7C7C7` / `#2A2A2A` | `NEW`, Draft, Undecided, Cancelled |
| Blue | `#0B5FB0` / `#E6F1FD` | `#7DB8F7` / `#10263D` | `ANSWER`, `RECONTACTED`, Registered, Queued |
| Green | `#1E7D47` / `#E4F5EA` | `#6FD49A` / `#16301F` | Valid Lead, Attend, QR Active, Sent, First Entry, Synced |
| Amber | `#8A5A00` / `#FFF4DB` | `#F2C14E` / `#33270A` | `NO_ANSWER`, `RETRY_NO_ANSWER`, Under Consideration, Overdue, Pending sync, Repeat Entry |
| Red | `#B42318` / `#FDEBEA` | `#F58A80` / `#3A1714` | Invalid, Not Attend, Hang Up Immediately, QR Revoked, Failed, Rejected |

Mapping lives in one file (`packages/ui/src/status.ts`) so a status never gets two colors in two screens.

## Typography

- Typeface: **Inter** (variable), self-hosted. Reason: it is the typeface of Frappe v15 and of the reference screenshot; matching it is what makes the app feel like ERPNext (R-06 reason written).
- Tabular numbers (`font-variant-numeric: tabular-nums`) on Registration IDs, phone numbers, counts and dates, so columns line up.
- No uppercase tracked labels. Labels are sentence case, as in Frappe.

| Role | Size / line | Weight |
|---|---|---|
| Page title | 20 / 28 | 600 |
| Section heading (`Person ⌄`) | 16 / 24 | 600 |
| Body, input value, table cell | 14 / 20 | 400 |
| Field label | 13 / 18 | 400, `--ink-label` |
| Meta (timestamps, help text) | 12 / 16 | 400 |
| Scanner result | 32 / 40 | 600 |

## Spacing, radius, elevation

- Spacing scale (px): 4, 8, 12, 16, 20, 24, 32, 48. Form field gap: 16 vertical, 24 between columns. Section padding: 20 (desktop), 16 (mobile).
- Radius: `4px` checkbox, `8px` inputs, buttons, dropdowns, `12px` cards, dialogs, form container. Full radius only for indicator pills (it is the motif). No pill buttons.
- Elevation: everything flat. Shadow only on floating layers that sit above content: dropdown, popover, command bar, dialog, toast. Reason: those are the only things that cover other content.
- No gradients, no glass, no glow, no background patterns.

## Icons

Lucide via `lucide-react`, size 16, `stroke-width: 1.5`. Reason: Frappe's icon set is feather-based, and Lucide is the maintained fork of Feather, so the stroke style matches the target look (R-04 reason written). Icons appear only where they carry meaning: sidebar items, toolbar actions (filter, sort, refresh), chevrons, and the row actions. No decorative icons beside headings, no icons inside every button.

## Layout

### App shell (desk)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ [EMS]  Edition: IBTE2027 ⌄   Visitor Leads / IBTE2027000123   [Search or type a command  Ctrl+K]  [Bell] [Avatar] │
├────────────┬─────────────────────────────────────────────────────────┤
│ Sidebar    │ Page head: Title  [indicator]           [Secondary] [Primary] │
│ (workspace │─────────────────────────────────────────────────────────│
│  links)    │ Page body (list view or form view)                       │
└────────────┴─────────────────────────────────────────────────────────┘
```

- Top bar 48px: product name as text (`[LOGO]` placeholder until the owner supplies a logo, R-23), edition switcher, breadcrumbs, command bar, notifications, user menu (Theme, Logout).
- Sidebar 220px, collapsible. Items come from the user's permissions: only routes that exist and the user can open appear (R-24). Groups: CRM (Visitor Leads, My Calls, Follow-ups), Registration, Gate (Gates, Devices, Scan History), Reports, Setup (Exhibitions, Editions, Custom Fields, Users, Roles, Audit Log).
- Mobile (< 768px): sidebar becomes a drawer opened from a menu button in the top bar; command bar collapses to a search icon.

### List view (Frappe list)

```text
Visitor Leads                                         [Import] [+ Add Visitor Lead]
[Search name, email, phone] [Telemarketing Status ⌄] [Lead Owner ⌄] [Filter (2)] [Sort: Updated ⌄]
☐  Name ↓            Registration ID     Company      Country   Status          Owner   Updated
☐  Thò               TE202610294490      Không        Vietnam   ● Answer        test    2 h
```

- Standard filters inline (the three most used), the rest under "Filter". Active filters show as removable chips. Filters live in the URL.
- Row height 40px, line separators only (no zebra, no cards). Whole row is a link to the form.
- Selection checkbox reveals the bulk bar: Assign To, Export, Clear selection.
- Columns chosen for the agent's next decision: who is this, how to reach them, what happened last, who owns it. Not generic Name/Status/Date/Actions.
- Footer: `20 of 1,284` and page size 20 / 100 / 500 (real counts from the API).

### Form view (from the screenshot)

```text
Visitor Lead  TE202610294490  ● Answer  ● Registered      [Log Call] [Save  Ctrl+S]
[Person] [Registration] [Custom Fields]                       ← tabs
┌──────────────────────────────────────────────┬───────────────┐
│ Person ⌄                                     │ Assigned To   │
│ Date            Registration ID   Status     │ Follow-up     │
│ First Name *    Email *           Gender     │ Created by    │
│ Phone *         Company Name      Source     │ Modified      │
│ Job Title       Country           Lead Owner │               │
│ City            Website           Product Categories          │
│ Business Type   Branch            Comment    │               │
│                 Exhibition Type              │               │
│──────────────────────────────────────────────│               │
│ Verification ⌄                               │               │
│ ○ Valid Lead    Attend ⌄          ☐ B2B Matching              │
│ ○ Invalid       Type of Buyers ⌄  Updated At │               │
├──────────────────────────────────────────────┴───────────────┤
│ Activity  (calls, verification changes, assignments, emails, edits)  │
└──────────────────────────────────────────────────────────────┘
```

- 3 columns at ≥ 1024px, 2 at 768 to 1023px, 1 below 768px. Field order follows the screenshot exactly.
- Labels above inputs, required marked with `*` in `--required`, and the Email/Phone rule shown as help text under the pair: "Email or phone is required."
- Valid Lead / Invalid is a radio pair with a third "Undecided" option, because the two are mutually exclusive.
- Read-only fields (Registration ID, Updated At) use `--surface-input` with `--ink-muted` text and no focus.
- Dirty form shows "Not Saved" gray indicator next to the title, like Frappe.
- Right sidebar (≥ 1280px only; below that it moves under the form): assignment, next follow-up, created/modified info.
- Activity timeline at the bottom: one line per event with actor, action, relative time, and the before/after diff on expand.

### Dialogs

- "Log Call": Call Result (radio), Notes, Next Follow-up (date-time, optional). Primary: "Save Call".
- "Assign To": Agent select (or Round Robin with agent multi-select). Primary: "Assign".
- Close with Escape, focus trapped, focus returns to the trigger.

### Dashboard

Not a generic stat grid. Each role lands on the screen that answers its question:

| Role | Lands on | Question it answers |
|---|---|---|
| Telemarketing Agent | My Calls | Who do I call next? (overdue follow-ups first) |
| Telemarketing Manager | Team overview | Which agents are behind, and how many leads are unassigned? |
| Exhibition Admin | Edition overview | How many leads, registrations, QR emails failed? |
| Gate Supervisor | Gate live | Scans per gate this hour, devices with pending sync |

Numbers come from the API only. Chart titles state the question ("Valid entries per hour, today"). While loading: per-card skeleton matching the card size. Empty: say why and what to do ("No leads in IBTE2027 yet. Import an Excel file to start.").

## Copy

- English only for all system text. Sentence case.
- Buttons name the action and the object: "Save", "Log Call", "Assign To", "Resend QR Email", "Revoke QR", "Start Import", "Download Error Report". Never "Submit", "Get Started", "Learn More".
- Errors say what failed and what to do: "Email already used by IBTE2027000045 in this edition. Open that lead or use another email."
- No emoji, no em dashes in UI text.

## States (every data view)

| State | Pattern |
|---|---|
| Loading | Skeleton rows in the list (same row height); form shows field skeletons. Never a full-page spinner. |
| Empty (first run) | One sentence + one action, e.g. "No visitor leads yet." [Import Excel] [Add Visitor Lead] |
| Empty (filtered) | "No leads match these filters." [Clear Filters] |
| Error | What failed + Retry button; request ID shown in small text for support. |
| No permission | "You don't have access to this edition." No data leaked, no broken layout. |
| Saving | Primary button shows "Saving..." and is disabled; toast "Saved" on success. |
| Conflict (409 version) | "This lead was changed by someone else." [Reload] keeps the user's unsaved values visible for copy. |

## Interaction and keyboard

- `Ctrl/Cmd+K` command bar, `Ctrl/Cmd+S` save form, `Esc` close dialog, `↑/↓` move in list, `Enter` open row, `Space` toggle row selection.
- Visible focus ring on every interactive element: 2px `--focus`, 2px offset. Never `outline: none` without this replacement.
- Tap targets ≥ 44px on touch (`@media (pointer: coarse)`): inputs and buttons grow from 32px to 44px. Desktop stays dense at 32px.
- Motion: 120ms ease-out for popover/dialog open, none elsewhere. Respect `prefers-reduced-motion`.

## Scanner PWA

A separate app for gate staff on phones or tablets. Same tokens, larger scale. Mobile-first, portrait.

```text
┌──────────────────────────┐
│ Gate A · IBTE2027   ● Online / ● Offline (3 pending) │
│                          │
│     [ camera viewfinder ]│
│                          │
│ [Enter code manually]    │
└──────────────────────────┘
```

Result screen fills the whole viewport for 2 seconds, then returns to the camera (tap to dismiss early):

| Result | Background / text | Word shown |
|---|---|---|
| First entry | `#15803D` / white | FIRST ENTRY |
| Repeat entry | `#F5B400` / `#171717` | REPEAT ENTRY |
| Rejected | `#C4302B` / white | REJECTED + reason ("Other edition", "Revoked", "Unknown code") |

Color is never the only signal: the word, an icon (check, repeat, x), and a distinct vibration pattern accompany each result. Offline results add the line "Provisional, will confirm when online."

Header indicator: Online (green), Offline (amber) with pending count, Sync error (red) with a Retry button. Cache expiry warning appears 1 hour before expiry.

Large type (32px result word, 18px body), controls ≥ 56px, high contrast, works in bright daylight.

## Dial and lever summary

- Dial: ENERGY 1 / RHYTHM 1 / MOTION 1.
- Focal point per screen: list view = the table; form view = the Person section; scanner = the result word.
- Accent: primary button (ink black), one per screen.
- Motif: indicator pill + collapsible section header.
- Whitespace: 16/24 field grid inside sections, 32 between sections, dividers instead of cards.

## Decision log (R-31)

| Decision | Reason |
|---|---|
| Frappe/ERPNext look | Owner request; team and users already know Frappe. |
| Inter | Frappe v15's typeface; matches the reference screenshot. |
| Ink black primary, blue only for links/focus | Frappe v15 style; keeps color free for status meaning. |
| Filled grey inputs, no borders | Matches the screenshot; reduces line noise in dense forms. |
| Indicator pills | Frappe's status pattern; one shape for every status. |
| Lucide 16 / 1.5 | Feather lineage, same stroke as Frappe icons. |
| Flat surfaces, shadows only on overlays | Only overlays sit above content. |
| 3-column form grid | Screenshot layout; collapses to 2 and 1 for smaller screens. |
| Light + dark + system | Frappe parity; long shifts. |
| Uniform rhythm | Desk app; predictability speeds up data entry. |
| Full-screen colored scanner results | Gate staff read the result from arm's length in a crowd. |
