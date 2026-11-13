// Screenshots for the exhibitor user guide (docs/exhibitor-guide). Builds a demo exhibition through
// the desk API, then walks the portal as an exhibitor would: set password, contract, payments,
// order forms, review and send, returned, approved and paid. Needs `make portal` style servers.
//   EMS_URL=... PORTAL_URL=.../exhibitor EMS_EMAIL=... EMS_PASSWORD=... node e2e/guide-screenshots.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const DESK = process.env.EMS_URL ?? "http://localhost:5173";
const PORTAL = (process.env.PORTAL_URL ?? "http://localhost:5176/exhibitor").replace(/\/$/, "");
const OUT = process.env.OUT ?? "../../../docs/exhibitor-guide/img";
const EMAIL = process.env.GUIDE_EMAIL ?? "budi@majutekstil.example";
mkdirSync(OUT, { recursive: true });
const PDF = Buffer.from("%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n");
const day = (offset) => new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const desk = await (await browser.newContext()).newPage();
const ctx = await browser.newContext({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 2 });
const portal = await ctx.newPage();
const view = (name) => portal.screenshot({ path: `${OUT}/${name}.png` });
const full = (name) => portal.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
// Section shots: the sticky header and action bar would sit over the section, so they go flat first.
async function part(name, locator) {
  const style = await portal.addStyleTag({ content: "header, .sticky { position: static !important; box-shadow: none !important; }" });
  await locator.screenshot({ path: `${OUT}/${name}.png` });
  await style.evaluate((el) => el.remove());
}
const panel = (heading) => portal.locator("section").filter({ has: portal.getByRole("heading", { name: heading, exact: true }) }).first();
const settle = () => portal.waitForTimeout(400);

let csrf = "";
async function staff(method, path, body, retried = false) {
  const r = await desk.request.fetch(`${DESK}/api/v1${path}`, { method, headers: { "X-CSRF-Token": csrf }, data: body });
  if (r.status() === 404 && !retried) {
    await desk.waitForTimeout(300);
    return staff(method, path, body, true);
  }
  if (!r.ok()) throw new Error(`${method} ${path}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
}

try {
  // --- demo data through the desk API ---------------------------------------------------------
  await desk.goto(`${DESK}/login`);
  await desk.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await desk.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await desk.getByRole("button", { name: "Sign In" }).click();
  await desk.waitForURL(/\/app/);
  csrf = (await staff("GET", "/auth/me")).csrf_token;

  let exhibition;
  for (const code of ["INATEX", "INATEXG", "INATEXGD"]) {
    exhibition = await staff("POST", "/exhibitions", { code, name: "INATEX" }).catch(() => null);
    if (exhibition) break;
  }
  if (!exhibition) throw new Error("no free exhibition code");
  const edition = await staff("POST", "/editions", {
    exhibition_id: exhibition.id, year: 2027, name: "INATEX 2027", city: "Jakarta", start_date: day(40), end_date: day(43), timezone: "Asia/Jakarta", default_currency: "IDR",
    price_regular_from: day(-5), price_regular_to: day(20), price_surcharge_from: day(21), price_surcharge_to: day(39), price_onsite_from: day(40), price_onsite_to: day(43),
  });
  const f04 = await staff("POST", "/order-forms", {
    edition_id: edition.id, code: "04", title: "Electrical Fittings & Supplies", has_catalog: true, allow_custom_items: true,
    attachment_purposes: ["FITTING_LOCATION"], deadline_on: day(14), sort_order: 4,
    instructions: "Prices include installation and dismantling. Orders cannot be refunded after the deadline.",
  });
  await staff("POST", `/order-forms/${f04.id}/items`, { section: "A. Lighting", code: "04-1", name: "Spotlight", size: "100 W", price_regular: "350000", max_quantity: 10 });
  await staff("POST", `/order-forms/${f04.id}/items`, { section: "A. Lighting", code: "04-2", name: "Fluorescent lamp", size: "40 W", price_regular: "275000" });
  const power = await staff("POST", `/order-forms/${f04.id}/items`, { section: "B. Power", code: "04-3", name: "Power socket", size: "2 A", price_regular: "650000" });
  await staff("PUT", `/order-forms/${f04.id}/items/${power.id}/allowances`, { tiers: [{ min_area_sqm: "0", free_quantity: 1 }] });
  await staff("PATCH", `/order-forms/${f04.id}`, { is_published: true, version: f04.version });

  const f07 = await staff("POST", "/order-forms", { edition_id: edition.id, code: "07", title: "Furniture & Display Rental", has_catalog: true, deadline_on: day(20), sort_order: 7 });
  await staff("POST", `/order-forms/${f07.id}/items`, { code: "07-1", name: "Folding chair", price_regular: "85000" });
  await staff("POST", `/order-forms/${f07.id}/items`, { code: "07-2", name: "Information counter", size: "100 x 50 cm", price_regular: "450000" });
  await staff("PATCH", `/order-forms/${f07.id}`, { is_published: true, version: f07.version });

  await staff("POST", "/order-forms", { edition_id: edition.id, code: "09", title: "Exhibitor Badges & Visa", details_type: "badges_visa", deadline_on: day(25), is_published: true, sort_order: 9 });

  const f11 = await staff("POST", "/order-forms", { edition_id: edition.id, code: "11", title: "Internet Connection", has_catalog: true, deadline_on: day(5), sort_order: 11 });
  await staff("POST", `/order-forms/${f11.id}/items`, { code: "11-1", name: "Wired internet", size: "20 Mbps", price_regular: "1500000" });
  await staff("PATCH", `/order-forms/${f11.id}`, { is_published: true, version: f11.version });

  const booth = await staff("POST", "/booths", { edition_id: edition.id, code: "B12", area_sqm: "18", price: "45000000" });
  let lead = await staff("POST", "/exhibitor-leads", { edition_id: edition.id, company_name: "PT Maju Tekstil Nusantara", contact_name: "Budi Santoso", email: EMAIL });
  lead = await staff("POST", `/exhibitor-leads/${lead.id}/stage`, { stage: "OPPORTUNITY", version: lead.version });
  lead = await staff("PUT", `/exhibitor-leads/${lead.id}/booth`, { booth_id: booth.id, version: lead.version });
  const converted = await staff("POST", `/exhibitor-leads/${lead.id}/convert`, { version: lead.version });
  const invite = new URL(converted.invitation.url);

  // --- 1. first sign-in from the invitation ---------------------------------------------------
  await portal.goto(`${PORTAL}${invite.pathname.replace(/^\/exhibitor/, "")}${invite.search}`);
  await portal.getByLabel("New Password", { exact: false }).first().fill("Guide-Password-2027");
  await portal.getByLabel("Confirm Password", { exact: false }).fill("Guide-Password-2027");
  await settle();
  await view("01-set-password");
  await portal.getByRole("button", { name: /Set Password/ }).click();
  await portal.getByRole("heading", { name: "My Exhibitions" }).waitFor();
  await settle();
  await view("02-home");

  // --- 2. exhibition page and contract --------------------------------------------------------
  await portal.getByRole("link", { name: /Open exhibition/ }).first().click().catch(() => portal.getByText("INATEX 2027").first().click());
  await portal.getByLabel("PIC Name").waitFor();
  await settle();
  await view("03-exhibition");
  await portal.getByLabel("PIC Name").fill("Budi Santoso");
  await portal.getByLabel("Tax ID (NPWP)").fill("01.234.567.8-901.000");
  await portal.getByLabel("Company Address").fill("Jl. Industri Raya No. 12, Bandung, Jawa Barat 40225");
  await portal.getByRole("button", { name: "Save Details" }).click();
  await portal.getByText("Save the PIC name and company address first.").waitFor({ state: "detached" });
  await settle();
  await part("04-contract-details", portal.locator("section#contract"));
  await portal.getByLabel("Signed PDF (up to 10 MB)").setInputFiles({ name: "contract-signed.pdf", mimeType: "application/pdf", buffer: PDF });
  await portal.getByRole("button", { name: "Upload Signed Contract" }).click();
  await portal.getByRole("button", { name: "Upload Signed Contract" }).waitFor({ state: "detached" });
  await settle();
  await part("05-contract-signed", portal.locator("section#contract"));

  // Staff record the first booth installment and verify it.
  const p1 = await staff("POST", `/exhibitor-leads/${lead.id}/payments`, { amount: "22500000", paid_on: day(0), method: "BANK_TRANSFER", reference: "Installment 1" });
  await staff("POST", `/exhibitor-leads/${lead.id}/payments/${p1.id}/review`, { decision: "VERIFIED", version: p1.version });
  await portal.reload();
  await portal.locator("section#payments").waitFor();
  await settle();
  await portal.evaluate(() => window.scrollTo(0, 0));
  await part("06-checklist", portal.getByRole("region", { name: "Your checklist" }));
  await part("07-payments", portal.locator("section#payments"));

  // --- 3. order forms -------------------------------------------------------------------------
  await portal.getByRole("button", { name: "Open Order Forms" }).click();
  await portal.getByRole("heading", { name: "Order Forms" }).waitFor();
  await settle();
  await view("08-forms-list");

  await portal.getByRole("link", { name: /Electrical Fittings/ }).click();
  await portal.getByRole("heading", { name: /^Electrical Fittings/ }).waitFor();
  await portal.getByLabel("Quantity of Spotlight").fill("4");
  await portal.getByLabel("Quantity of Fluorescent lamp").fill("2");
  await portal.getByRole("button", { name: "Add Extra Item" }).click();
  await portal.getByLabel("Extra item 1", { exact: true }).fill("LED strip, warm white");
  await portal.getByLabel("Size", { exact: true }).fill("5 m");
  await portal.getByLabel("Quantity", { exact: true }).fill("2");
  await portal.getByLabel("Remarks").fill("Please install the spotlights before the move-in day.");
  await portal.getByRole("button", { name: "Save Draft" }).click();
  await portal.getByText("Draft saved.", { exact: false }).waitFor();
  await portal.getByLabel("Add Fitting Location").setInputFiles({ name: "booth-B12-layout.pdf", mimeType: "application/pdf", buffer: PDF });
  await portal.getByRole("button", { name: "Upload", exact: true }).last().click();
  await portal.getByRole("button", { name: "booth-B12-layout.pdf", exact: true }).waitFor();
  await portal.evaluate(() => window.scrollTo(0, 0));
  await settle();
  await view("09-form-top");
  await part("10-items", panel("Items"));
  await part("11-extra", panel("Extra Items"));
  await part("12-attachments", panel("Attachments"));
  await portal.getByText("Estimated total").locator("xpath=ancestor::div[contains(@class,'sticky')][1]").screenshot({ path: `${OUT}/13-action-bar.png` });

  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByRole("heading", { name: /Review Order/ }).waitFor();
  await settle();
  await full("14-review");
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText("sent.", { exact: false }).first().waitFor();
  await portal.evaluate(() => window.scrollTo(0, 0));
  await settle();
  await full("15-sent");

  // Staff price the extra item and return the order with a note.
  const list = await staff("GET", `/exhibitor-orders?edition_id=${edition.id}`);
  const orderId = list.items[0].id;
  let order = await staff("GET", `/exhibitor-orders/${orderId}`);
  const extra = order.lines.find((l) => !l.item_id);
  order = await staff("PATCH", `/exhibitor-orders/${orderId}/lines/${extra.id}`, { unit_price: "175000", version: order.version });
  order = await staff("POST", `/exhibitor-orders/${orderId}/review`, { decision: "RETURNED", notes: "Please add one power socket for the spotlights. The first socket is free with your booth.", version: order.version });
  await portal.reload();
  await portal.getByText("Please add one power socket", { exact: false }).waitFor();
  await settle();
  await view("16-returned");
  await portal.getByLabel("Quantity of Power socket").fill("1");
  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText("sent.", { exact: false }).first().waitFor();

  // Staff approve and record a partial payment, verified.
  order = await staff("GET", `/exhibitor-orders/${orderId}`);
  order = await staff("POST", `/exhibitor-orders/${orderId}/review`, { decision: "APPROVED", version: order.version });
  const op = await staff("POST", `/exhibitor-orders/${orderId}/payments`, { amount: "1000000", paid_on: day(0), method: "BANK_TRANSFER", reference: "TRX-0412" });
  await staff("POST", `/exhibitor-orders/${orderId}/payments/${op.id}/review`, { decision: "VERIFIED", version: op.version });
  await portal.reload();
  await portal.getByText("Still to pay").waitFor();
  await settle();
  await full("17-approved");

  // --- 4. a questions form, and "I don't require this form" ----------------------------------
  await portal.goto(`${PORTAL}/e/${lead.id}/forms/09`);
  await portal.getByRole("heading", { name: /^Exhibitor Badges/ }).waitFor();
  await portal.getByLabel("Indonesian company").check();
  await portal.getByRole("button", { name: "Add Badge" }).click();
  await portal.getByLabel("Full name 1").fill("Budi Santoso");
  await portal.getByLabel("Gender 1").selectOption("MALE");
  await portal.getByLabel("Designation 1").fill("Sales Manager");
  await portal.getByRole("button", { name: "Add Badge" }).click();
  await portal.getByLabel("Full name 2").fill("Siti Rahmawati");
  await portal.getByLabel("Gender 2").selectOption("FEMALE");
  await portal.getByLabel("Designation 2").fill("Marketing");
  await settle();
  await part("18-questions", panel("Badges and Visa"));
  await portal.getByRole("button", { name: "Save Draft" }).click();
  await portal.getByText("Draft saved.", { exact: false }).waitFor();

  await portal.goto(`${PORTAL}/e/${lead.id}/forms/07`);
  await portal.getByRole("heading", { name: /^Furniture/ }).waitFor();
  // The tick saves first, then the form reloads ticked.
  await portal.getByLabel("I don't require this form").click();
  await portal.waitForFunction(() => document.querySelector("input[type=checkbox]")?.checked === true);
  await settle();
  await part("19-not-required", portal.getByLabel("Remarks").locator("xpath=ancestor::section[1]"));

  await portal.goto(`${PORTAL}/e/${lead.id}/forms`);
  await portal.getByRole("heading", { name: "Order Forms" }).waitFor();
  await settle();
  await view("20-forms-progress");

  // --- 5. on a phone ----------------------------------------------------------------------------
  await portal.setViewportSize({ width: 390, height: 844 });
  await portal.goto(`${PORTAL}/e/${lead.id}/forms`);
  await portal.getByRole("heading", { name: "Order Forms" }).waitFor();
  await settle();
  await view("21-phone-forms");
  await portal.goto(`${PORTAL}/e/${lead.id}/forms/11`);
  await portal.getByRole("heading", { name: /^Internet/ }).waitFor();
  await portal.getByLabel("Quantity of Wired internet").fill("1");
  await settle();
  await view("22-phone-form");

  // --- 6. signing in later --------------------------------------------------------------------------
  await portal.setViewportSize({ width: 1200, height: 800 });
  await portal.getByRole("button", { name: "Sign Out" }).click();
  await portal.getByRole("button", { name: "Sign In" }).waitFor();
  await portal.getByLabel("Email").fill(EMAIL);
  await portal.getByLabel("Password").fill("Guide-Password-2027");
  await settle();
  await view("00-sign-in");
  console.log(`done: ${edition.code}, lead ${lead.id}`);
} catch (e) {
  console.log(`FAIL ${String(e).split("\n")[0]}`);
  await portal.screenshot({ path: `${OUT}/failed.png`, fullPage: true }).catch(() => {});
  process.exitCode = 1;
} finally {
  await browser.close();
}
