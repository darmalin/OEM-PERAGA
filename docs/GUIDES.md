# User guides (PDF)

Two guides in Bahasa Indonesia, with screenshots of the real app (demo edition INATEX 2027):

| Guide | For | Source | PDF |
|---|---|---|---|
| Panduan Portal Exhibitor | exhibitors | `exhibitor-guide/guide.html` | `exhibitor-guide/Panduan-Portal-Exhibitor-PERAGA-Expo.pdf` |
| Panduan Admin Exhibitor | PERAGA staff | `admin-guide/guide.html` | `admin-guide/Panduan-Admin-Exhibitor-PERAGA-Expo.pdf` |

## Rebuilding after the app changes

Needs the API, the desk (`EMS_URL`) and the portal (`PORTAL_URL`) running, the dev admin from `.env`,
and a local Chromium. Run in this order (each builds on the demo data of the one before):

1. `frontend/apps/exhibitor`: `node e2e/guide-screenshots.mjs` (portal shots, `exhibitor-guide/img`).
2. `frontend/apps/web`: `node e2e/guide-screenshots.mjs` (desk shots, `admin-guide/img`).
3. `frontend/apps/web`: `node e2e/guide-quotations.mjs` (booth search and quotation shots).
4. Desk shots are cropped into `admin-guide/img/c/`: the 348 px sidebar and the 62 px top bar off
   (at device scale 1.5), the empty bottom trimmed, and a few tall pages cut to the part the step is
   about. Element shots (`02`, `13`, `23`) and `q10-pdf.png` are used as they are.
5. `frontend/apps/exhibitor`: `node e2e/guide-pdf.mjs` for the exhibitor guide, and
   `node e2e/guide-pdf.mjs admin-guide Panduan-Admin-Exhibitor-PERAGA-Expo.pdf "Panduan Admin Exhibitor"`.

The PDF script prints the cover without a page footer and joins it with the body using `pdfunite`
(poppler-utils). Screenshots show a placeholder signature, not a real one.
