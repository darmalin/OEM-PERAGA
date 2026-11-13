# 13 Exhibitor Order Forms (built 2026-11-09)

Owner request 2026-11-09, built in phases 1 to 8 of
[docs/EXHIBITOR_ORDER_FORMS.md](../docs/EXHIBITOR_ORDER_FORMS.md), which holds the decisions, the data
model, the task list, and the map of the old portal's fourteen forms. This file is the short version.

Spec §1.2 put "the twelve exhibitor forms" outside phase 1; the owner moved them in. Invoices,
refunds, credit notes, and a payment gateway stay out.

## Flow

Convert (portal account) → exhibitor opens Order Forms in the portal → fills a form (draft) → sends
it → staff review (price extra items, Approve or Return) → staff record and verify payments → Paid.

One generic module (`app/modules/orders`), not one table per form: a form is a catalog with prices,
extra items, a code-defined question set, attachments, or a mix.

## Decisions (2026-11-09)

| # | Decision |
|---|---|
| O1 | In scope as its own slice. |
| O2 | Exhibitors fill and send right after Convert; orders that cost money are approved only once the booth contract is signed. |
| O3 | Approved orders are paid with the same payment tagging as the contract. |
| O4 | Regular, Surcharge, and Onsite prices; the period comes from the edition's price dates on the submit day (edition timezone); a missing price uses Regular. |
| O5 | Catalog prices are final; no tax. |
| O6 | Extra items have no price from the exhibitor; staff set it during review. |
| O7 | One open order per form; sent orders do not change; Returned goes back to the exhibitor; more is a new order. |
| O8 | Deadline is shown with a countdown; submitting closes after `closes_on` (default the edition's Order Expired date). |
| O9 | Free quantities per catalog item by booth area, once per exhibitor across orders. |
| O10 | Question sets are defined in code; staff set only their choices per form. |
| O11 | No email notifications yet; statuses show in the portal and the desk. |
| O12 | New permissions `order_form.manage` and `exhibitor_order.review`. |

## What is built

**Desk (menu Exhibitors)**
- Order Forms (`order_form.manage`): forms per edition, catalog items with pictures, Excel import of
  the catalog, Copy from Edition, choices of the questions, free quantities by booth size. A form is
  published only when there is something to fill.
- Orders (`exhibitor_lead.read`, in the caller's lead scope): queue of sent orders with flags (extra
  items to price, contract not signed, booth changed, payment state), order page with lines,
  answers, attachments, Approve / Return to Exhibitor / Cancel (`exhibitor_order.review`), payments
  (`exhibitor_payment.record` / `.verify`), Excel export per form.
- Lead page: Orders tab (progress on each form and the orders sent). Overview: Service orders row.

**Exhibitor portal**
- Order Forms from the exhibition page; list with deadlines, progress, and filters; each form with the
  catalog at today's price, extra items, questions, attachments, remarks, "I don't require this form";
  Save Draft, Review and Send, Order More; sent orders with their status and payments.

## Rules worth knowing

- The portal never sends prices, totals, statuses, or the price period; the server computes them.
  Prices, the period, the booth, and its area are fixed when an order is sent.
- Order numbers are `<edition code>-O-0001`, given on the first submit (a returned order keeps it).
- Drafts are private to the exhibitor; staff never list them.
- Answers keep the chosen text, so editing the choices never changes a sent order. Unchanged extra
  items keep their staff price when a returned order is sent again.
- A cancel is blocked while the order has pending or verified payments.
- Payments for orders live in `exhibitor_payments` with `order_id` (migration 0034); every payment has
  exactly one target, and contract payment totals never include order payments.

Migrations 0030 to 0034. Tests: `tests/test_order_*.py`. E2E: `make e2e-order-forms` (desk setup) and
`make e2e-portal-orders` (portal and desk review, needs `make portal`).

## Sample forms

`backend/scripts/seed_sample_order_forms.py` fills an edition with the old portal's fourteen forms
(titles, notes, 72 catalog items at the old prices, choices, free badges and parking passes), so the
client sees familiar forms before the new price list arrives. It goes through the desk API as a staff
user with `order_form.manage`; a form number already in the edition is kept and only its missing items
are added. Deadlines: forms 01 to 03 four weeks before the show, the rest three weeks; check them in
Settings afterwards. Form 10 (seminar) is priced in USD.

```bash
cd backend
EMS_URL=http://localhost:8000 EMS_EMAIL=... EMS_PASSWORD=... \
  uv run python -m scripts.seed_sample_order_forms --edition INATEX2027
```

For staging, run it from a laptop with `EMS_URL=https://<staging domain>` (the production image does not
carry `scripts/`). `--dry-run` lists what would be added, `--draft` keeps new
forms unpublished, `--images` also copies item pictures from the old portal (peragaexpo.com).

## Known gaps

In `BACKEND_RULES/known-gaps.md` (B3, F9 to F11) and `FRONTEND_RULES/known-gaps.md` (W18 to W20). The
catalog of the next edition is not loaded yet: it waits for the owner's price list.
