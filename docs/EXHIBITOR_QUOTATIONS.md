# Exhibitor Quotations and Booth Pricing

Owner request 2026-11-13: choose a booth by searching (or type a new one), let staff change the price,
and make quotations, with their history, before a lead becomes an exhibitor. Source: the sales team's
Excel quotations `IITINA2027 Quotation SS + booking fee.xlsx` and `IITINA2027 Quotation RS + booking
fee.xlsx` (sheets IIT IDR, IIT USD, INA IDR, INA USD).

## What the Excel quotation holds

| Part | Example |
|---|---|
| Number | `112/PNJS/IIT/VII/2026`: running number / company (PT Peraga Nusantara Jaya Sakti) / quotation code / month in Roman numerals / year. INATEX quotations also use `IIT`. |
| Date | `Jakarta, July 22, 2026` |
| Recipient | company name, two address lines, `Dear, Ms. Novy,` |
| Stand type | `RAW SPACE` or `SHELL SCHEME`. Shell scheme includes partition, folding chair, company name, reception desk, 2 A / 220 V. |
| Space | width x length in metres (decimals, e.g. 15.5 x 18 = 279 sqm); optional complimentary space (21 sqm), so 258 sqm is charged |
| Rates | per sqm, per stand type and currency, e.g. INA IDR raw 4,850,000 / shell 5,100,000; INA USD raw 365 / shell 395 |
| Discount | `Special Discount` or `Early Bird`, a percentage **of the raw space cost**, also for shell scheme |
| Tax | IDR: VAT 12% on a tax base of 11/12 (11% in effect). USD: none. |
| Terms | three payments with percentages and dates: Booking Fee 30%, First Payment 50%, Last Payment 20% (labels vary) |
| Closing | thank-you line, `Your Faithfully,`, signature image, `Sephy Yusianty`, `Sales & Marketing` |
| Letterhead | PERAGA Expo logo, `PT. PERAGA NUSANTARA JAYA SAKTI`, office address, phone, e-mail, website |

### Calculation (checked against the APR sheet)

```
charged sqm   = width x length - complimentary sqm            279 - 21 = 258
discount      = charged sqm x raw rate x discount %           258 x 5,050,000 x 25% = 325,725,000
cost          = charged sqm x stand rate - discount           1,302,900,000 - 325,725,000 = 977,175,000
VAT           = cost x tax base x VAT rate (IDR only)          977,175,000 x 11/12 x 12% = 107,489,250
total         = cost + VAT                                     1,084,664,250
each term     = total x term %; the last term takes the rounding remainder
```

Amounts are rounded to 2 decimals, half up.

## Decisions (owner, 2026-11-13: all defaults)

| # | Decision |
|---|---|
| Q1 | A booth code typed in the picker is added to Booths when saved (it is still sold once). Needs `booth.manage`. |
| Q2 | The price is the lead's agreed price, editable by staff who can update the lead; a Draft contract follows it and its Booth Price is editable; a Signed contract is locked (Reopen first). |
| Q3 | A quotation needs the space size; the booth code is optional. |
| Q4 | Numbers run per quotation code per year, from a starting number staff set (the Excel numbers already used). |
| Q5 | The server renders the quotation as a PDF laid out like the Excel sheet. No Excel output. |
| Q6 | The signer (name, title, signature image) is set per edition, not per user. |
| Q7 | The PNJS letterhead is one fixed image for every edition. |
| Q8 | VAT is on by default for IDR and off for USD; staff can change it per quotation. |
| Q9 | Accepting a quotation sets the lead's booth price; at Convert the contract takes the quotation's price, discount, VAT, and payment terms. |
| Q10 | No e-mail: staff download the PDF and send it themselves. |

## Phases

1. **Booth picker and price.** Search combobox on Choose Booth (code or hall), "Add booth" for a code
   not listed, agreed price per lead (`exhibitor_leads.booth_price`, migration 0035), editable Booth
   Price on a Draft contract.
2. **Settings and model.** Edition quotation settings (code, starting number, letter name, rates,
   shell scheme includes, default terms, VAT, signer); `exhibitor_quotations` with frozen inputs and
   computed amounts; number counter; API to preview and create; history per lead.
3. **Screens and PDF.** Quotations tab on the lead: history, New Quotation with a live summary before
   Create, download PDF; edition settings page.
4. **Accept and contract.** Accept one quotation (others stay as history); the contract at Convert
   takes its amounts, VAT, and terms.
5. **Docs.** Feature summary, admin guide chapter and screenshots, E2E.

## Data model

- `exhibitor_leads.booth_price`: agreed price of the held booth (null: the list price applies). A
  price needs a booth (`ck_exhibitor_leads_booth_price_with_booth`).
- Quotations are never edited once created. A revision is a new quotation with a new number; the
  previous one is marked Superseded. Statuses: `ISSUED`, `SUPERSEDED`, `ACCEPTED`, `CANCELLED`.
- Each quotation stores what was printed: recipient, stand type, sizes, rates, discount, VAT
  settings, terms, signer, and the computed amounts, so later setting changes never alter it.
