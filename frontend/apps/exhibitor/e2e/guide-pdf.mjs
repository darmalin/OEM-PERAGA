// Prints a guide page in docs/ to PDF. Exhibitor guide by default; the admin guide with
//   node e2e/guide-pdf.mjs admin-guide Panduan-Admin-Exhibitor-PERAGA-Expo.pdf "Panduan Admin Exhibitor"
import { execFileSync } from "node:child_process";
import { rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright-core";

const [guide = "exhibitor-guide", file = "Panduan-Portal-Exhibitor-PERAGA-Expo.pdf", footer = "Panduan Portal Exhibitor"] = process.argv.slice(2);
const dir = fileURLToPath(new URL(`../../../../docs/${guide}/`, import.meta.url));
const out = process.env.OUT ?? `${dir}${file}`;

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const page = await browser.newPage();
await page.goto(pathToFileURL(`${dir}guide.html`).href, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
// The cover prints without the page footer; the body with it. pdfunite (poppler) joins them.
const base = { format: "A4", printBackground: true, preferCSSPageSize: true };
await page.pdf({ ...base, path: `${out}.cover`, pageRanges: "1" });
await page.pdf({
  ...base,
  path: `${out}.body`,
  pageRanges: "2-",
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: `<div style="width:100%;padding:0 16mm;font:8px Inter,sans-serif;color:#5b5e80;display:flex;justify-content:space-between">
    <span>${footer} · PERAGA Expo</span><span>Halaman <span class="pageNumber"></span></span></div>`,
});
execFileSync("pdfunite", [`${out}.cover`, `${out}.body`, out]);
rmSync(`${out}.cover`);
rmSync(`${out}.body`);
await browser.close();
console.log(out);
