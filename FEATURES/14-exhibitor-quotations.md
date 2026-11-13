# 14 Exhibitor Quotations and Booth Pricing (built 2026-11-13)

Owner request 2026-11-13, built in phases 1 to 5 of
[docs/EXHIBITOR_QUOTATIONS.md](../docs/EXHIBITOR_QUOTATIONS.md), which holds the decisions (Q1 to
Q10), the Excel quotation it follows, the calculation, and the data model. This file is the short
version.

## Flow

Lead → **Quotation** (New Quotation, summary, Create, Download PDF, Revise or Cancel) → **Accept** →
Opportunity holds the booth at the quoted price → Convert → the contract takes the quotation's price,
discount, VAT, and terms → payments count against the total with VAT.

## What is built

**Booth and price**
- Choose Booth is a search box (code or hall) over the free booths. Booth managers can type a code
  that is not listed and add it with hall, area, and price (it joins Booths, so it is still sold once).
- The lead keeps an agreed booth price (`exhibitor_leads.booth_price`, migration 0035), starting at
  the list price and editable ("Change Booth or Price"). A Draft contract's Booth Price is editable and
  the lead follows it; a signed contract stays locked.

**Quotations** (`app/modules/quotations`, migrations 0036 and 0037)
- Exhibitors → Quotation Settings (`booth.manage`): code and Start From, company code, place, letter
  name and event line, rates per sqm (raw space, shell scheme; IDR, USD), shell scheme inclusions,
  discount label, VAT (12% on 11/12), default terms, signer and signature image.
- Lead → Quotations tab (`exhibitor_lead.read`; create and act with `exhibitor_lead.update`, any stage
  but Lost): history; New Quotation with a live summary and the number it would get; quotation page
  with Download PDF (PNJS letterhead, layout of the Excel sheet), Revise (new number, old one
  Superseded), Cancel Quotation (with a reason), and Accept.
- Accept: one accepted quotation per lead; the lead holds the quoted booth when it can; the contract
  (Draft now, or at Convert) takes price, discount, VAT, and terms. Desk and portal show the VAT, the
  quotation number, and the terms.

## Rules worth knowing

- Numbers `113/PNJS/IIT/XI/2026` run per code and year from Start From; editions with the same code
  share them. A preview takes no number.
- A quotation is never edited; it stores everything it printed (rates, letter text, signer,
  signature), so settings changes never alter a made quotation or its PDF.
- Amounts follow the Excel sheet: area minus complimentary space; discount as a share of the raw
  space cost, also for shell scheme; VAT on the 11/12 tax base for IDR; the last term takes the
  rounding remainder.
- Contract total = booth price - discount + VAT; editing the price or discount recomputes the VAT.

Tests: `tests/test_booth_price.py`, `tests/test_quotations.py` (amounts checked against the APR and
Yesun sheets), `tests/test_quotation_accept.py`. Admin guide: `docs/admin-guide` chapter 3.

## Known gaps

In `BACKEND_RULES/known-gaps.md` (F12 to F15, and B4 for the old `alembic check` drift) and
`FRONTEND_RULES/known-gaps.md` (W21, W22).
