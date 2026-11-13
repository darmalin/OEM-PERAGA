// Screenshots of booth search, agreed price, and quotations for the admin guide (docs/admin-guide).
// Builds on the INATEX 2027 demo of guide-screenshots.mjs (quotation settings saved, CV Benang Emas a
// Lead, PT Tenun Kreasi Bali an exhibitor with a Draft contract). Run after both guide scripts:
//   EMS_URL=... EMS_EMAIL=... EMS_PASSWORD=... node e2e/guide-quotations.mjs
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright-core";

const DESK = process.env.EMS_URL ?? "http://localhost:5173";
const OUT = process.env.OUT ?? "../../../docs/admin-guide/img";
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, reducedMotion: "reduce" })).newPage();
const settle = () => page.waitForTimeout(600);
const view = async (name) => { await settle(); await page.screenshot({ path: `${OUT}/${name}.png` }); };
const full = async (name) => { await settle(); await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }); };
const field = (label) => page.getByLabel(new RegExp(`^${label}`));
const visible = (locator) => locator.locator("visible=true").first();

try {
  await page.goto(`${DESK}/login`);
  await page.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await page.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL(/\/app/);
  const csrf = (await (await page.request.get(`${DESK}/api/v1/auth/me`)).json()).csrf_token;
  const eds = await (await page.request.get(`${DESK}/api/v1/editions?page_size=100`)).json();
  const ed = eds.items.find((e) => e.code === "INATEX2027");
  await page.evaluate((id) => localStorage.setItem("ems.edition", id), ed.id);
  const leads = await (await page.request.get(`${DESK}/api/v1/exhibitor-leads?edition_id=${ed.id}&page_size=100`)).json();
  let emas = leads.items.find((l) => l.company_name === "CV Benang Emas");
  const tenun = leads.items.find((l) => l.company_name === "PT Tenun Kreasi Bali");

  // Settings.
  await page.goto(`${DESK}/app/quotation-settings`);
  await field("Quotation Code").waitFor();
  await full("q01-settings");

  // Booth search and agreed price.
  if (emas.stage === "LEAD") {
    const r = await page.request.post(`${DESK}/api/v1/exhibitor-leads/${emas.id}/stage`, { headers: { "X-CSRF-Token": csrf }, data: { stage: "OPPORTUNITY", version: emas.version } });
    emas = await r.json();
  }
  await page.goto(`${DESK}/app/exhibitor-leads/${emas.id}/booth`);
  await page.getByRole("combobox").fill("C");
  await page.getByRole("option").first().waitFor();
  await view("q02-booth-search");
  await page.getByRole("combobox").fill("E05");
  await page.getByRole("option", { name: /Add booth/ }).click();
  await field("Hall").fill("Hall E");
  await field("Area").fill("36");
  await field("Agreed Price").fill("170000000");
  await view("q03-booth-new");
  await page.getByRole("button", { name: "Hold Booth" }).click();
  await page.waitForURL(new RegExp(`/exhibitor-leads/${emas.id}(\\?|$)`));
  await page.getByRole("link", { name: "Change Booth or Price" }).click();
  await field("Agreed Price").fill("165000000");
  await view("q04-booth-price");
  await page.getByRole("button", { name: "Save Price" }).click();
  await page.waitForURL(new RegExp(`/exhibitor-leads/${emas.id}(\\?|$)`));

  // A quotation with the summary, then the PDF.
  await page.goto(`${DESK}/app/exhibitor-leads/${emas.id}?tab=quotations`);
  await page.getByRole("link", { name: "New Quotation" }).click();
  await field("Address").fill("Jl. Raya Solo-Sragen Km 9\nKaranganyar, Jawa Tengah 57722");
  await field("Attention").fill("Ms. Dewi");
  await field("Width").fill("6");
  await field("Length").fill("6");
  await field("Discount \\(%\\)").fill("15");
  await visible(page.getByText(/^Summary · \d+\//)).waitFor();
  await full("q05-new");
  await page.getByRole("button", { name: "Create Quotation" }).click();
  await page.getByRole("heading", { name: /^Quotation \d+\// }).waitFor();
  await view("q06-detail");
  const url = page.url();
  const qid = url.split("/quotations/")[1].split(/[/?]/)[0];
  const pdf = await page.request.get(`${DESK}/api/v1/quotations/${qid}/pdf`);
  writeFileSync(`${OUT}/q-sample.pdf`, await pdf.body());
  execFileSync("pdftoppm", ["-r", "110", "-png", "-singlefile", `${OUT}/q-sample.pdf`, `${OUT}/q10-pdf`]);

  await page.getByRole("link", { name: "Accept" }).click();
  await page.getByRole("button", { name: "Accept Quotation" }).waitFor();
  await view("q07-accept");
  await page.getByRole("button", { name: "Accept Quotation" }).click();
  await visible(page.getByText(/^Accepted /)).waitFor();

  await page.goto(`${DESK}/app/exhibitor-leads/${emas.id}?tab=quotations`);
  await visible(page.getByText("Accepted")).waitFor();
  await view("q08-history");

  await page.goto(`${DESK}/app/exhibitor-leads/${tenun.id}?tab=contract`);
  await page.getByText("Terms of payment from the quotation").waitFor();
  await view("q09-contract-vat");
  console.log("done");
} catch (e) {
  console.log(`FAIL ${String(e).split("\n")[0]}`);
  await page.screenshot({ path: `${OUT}/failed.png`, fullPage: true }).catch(() => {});
  process.exitCode = 1;
} finally {
  await browser.close();
}
