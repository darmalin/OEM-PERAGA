// Screenshots for the admin (desk) guide in docs/admin-guide. Builds on the INATEX 2027 demo that
// frontend/apps/exhibitor/e2e/guide-screenshots.mjs creates (run that first), then walks the desk
// as staff would: booths, leads to exhibitor, contract and payments, order forms, order review.
//   EMS_URL=... PORTAL_URL=.../exhibitor EMS_EMAIL=... EMS_PASSWORD=... node e2e/guide-screenshots.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const DESK = process.env.EMS_URL ?? "http://localhost:5173";
const PORTAL = (process.env.PORTAL_URL ?? "http://localhost:5176/exhibitor").replace(/\/$/, "");
const OUT = process.env.OUT ?? "../../../docs/admin-guide/img";
const SECOND = process.env.GUIDE_EMAIL2 ?? "rina@nusantarafabrics.example";
mkdirSync(OUT, { recursive: true });
const PDF = Buffer.from("%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n");
const day = (offset) => new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, reducedMotion: "reduce" });
const page = await ctx.newPage();
const portal = await (await browser.newContext({ viewport: { width: 1200, height: 800 } })).newPage();

const settle = () => page.waitForTimeout(500);
const view = async (name) => { await settle(); await page.screenshot({ path: `${OUT}/${name}.png` }); };
const full = async (name) => { await settle(); await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }); };
// The innermost section around a heading, with sticky bars laid flat so they do not cover it.
const box = (heading) => page.locator("section").filter({ has: page.getByRole("heading", { name: heading, exact: true }) }).last();
async function part(name, locator) {
  await settle();
  const style = await page.addStyleTag({ content: "header, .sticky, [class*='sticky'] { position: static !important; }" });
  await locator.screenshot({ path: `${OUT}/${name}.png` });
  await style.evaluate((el) => el.remove());
}
// A collapsible form section (ui/field.tsx Section) by its title, or a panel by its heading.
async function area(title) {
  if (await box(title).count()) return box(title);
  return page.getByRole("button", { name: title, exact: true }).locator("xpath=ancestor::div[contains(@class,'border-b')][1]");
}
const field = (label) => page.getByLabel(new RegExp(`^${label}\\b`));

let csrf = "";
async function staff(method, path, body, retried = false) {
  const r = await page.request.fetch(`${DESK}/api/v1${path}`, { method, headers: { "X-CSRF-Token": csrf }, data: body });
  if (r.status() === 404 && !retried) {
    await page.waitForTimeout(300);
    return staff(method, path, body, true);
  }
  if (!r.ok()) throw new Error(`${method} ${path}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
}

try {
  await page.goto(`${DESK}/login`);
  await page.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await page.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL(/\/app/);
  csrf = (await staff("GET", "/auth/me")).csrf_token;

  const editions = await staff("GET", "/editions?page_size=100");
  const edition = editions.items.find((e) => e.code === "INATEX2027");
  if (!edition) throw new Error("run the exhibitor guide screenshots first (INATEX2027 demo)");
  await page.evaluate((id) => localStorage.setItem("ems.edition", id), edition.id);
  const leads = await staff("GET", `/exhibitor-leads?edition_id=${edition.id}&page_size=100`);
  const maju = leads.items.find((l) => l.company_name === "PT Maju Tekstil Nusantara");

  let nf = leads.items.find((l) => l.company_name === "PT Nusantara Fabrics");
  if (!nf) {
  // --- more demo data: booths, a lead pipeline, and a second exhibitor with an order to review ---
  for (const [code, hall, area, price] of [["A01", "Hall A", "9", "22500000"], ["A02", "Hall A", "9", "22500000"], ["A03", "Hall A", "12", "30000000"], ["B14", "Hall B", "18", "45000000"], ["C01", "Hall C", "36", "90000000"]]) {
    await staff("POST", "/booths", { edition_id: edition.id, code, hall, area_sqm: area, price });
  }
  const pipeline = [
    ["PT Sinar Garmen Indonesia", "Andi Wijaya", "andi@sinargarmen.example", "LEAD"],
    ["CV Benang Emas", "Dewi Lestari", "dewi@benangemas.example", "LEAD"],
    ["PT Indo Rajut Mandiri", "Hendra Gunawan", "hendra@indorajut.example", "OPPORTUNITY"],
  ];
  for (const [company, contact, email, stage] of pipeline) {
    let l = await staff("POST", "/exhibitor-leads", { edition_id: edition.id, company_name: company, contact_name: contact, email, phone: "+62 812 0000 1111", product_categories: "Textile, yarn" });
    if (stage === "OPPORTUNITY") l = await staff("POST", `/exhibitor-leads/${l.id}/stage`, { stage, version: l.version });
  }
    const booths = await staff("GET", `/booths?edition_id=${edition.id}&page_size=100`);
    const b14 = booths.items.find((b) => b.code === "B14");
  nf = await staff("POST", "/exhibitor-leads", { edition_id: edition.id, company_name: "PT Nusantara Fabrics", contact_name: "Rina Kusuma", email: SECOND });
  nf = await staff("POST", `/exhibitor-leads/${nf.id}/stage`, { stage: "OPPORTUNITY", version: nf.version });
  nf = await staff("PUT", `/exhibitor-leads/${nf.id}/booth`, { booth_id: b14.id, version: nf.version });
  const conv = await staff("POST", `/exhibitor-leads/${nf.id}/convert`, { version: nf.version });

  // The second exhibitor sends Form 04 with an extra item (contract not signed yet).
  const invite = new URL(conv.invitation.url);
  await portal.goto(`${PORTAL}${invite.pathname.replace(/^\/exhibitor/, "")}${invite.search}`);
  await portal.getByLabel("New Password", { exact: false }).first().fill("Guide-Password-2027");
  await portal.getByLabel("Confirm Password", { exact: false }).fill("Guide-Password-2027");
  await portal.getByRole("button", { name: /Set Password/ }).click();
  await portal.getByRole("heading", { name: "My Exhibitions" }).waitFor();
  await portal.goto(`${PORTAL}/e/${nf.id}/forms/04`);
  await portal.getByLabel("Quantity of Spotlight").fill("6");
  await portal.getByLabel("Quantity of Power socket").fill("2");
  await portal.getByRole("button", { name: "Add Extra Item" }).click();
  await portal.getByLabel("Extra item 1", { exact: true }).fill("Hanging banner lamp");
  await portal.getByLabel("Quantity", { exact: true }).fill("1");
  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText("sent.", { exact: false }).first().waitFor();

  }
  // FROM_ORDERS=1 reruns only the order screens once the earlier ones exist.
  if (!process.env.FROM_ORDERS) {
  // --- 1. overview and edition dates --------------------------------------------------------------
  await page.goto(`${DESK}/app`);
  await page.getByText("Service orders").waitFor();
  await view("01-overview");
  await page.goto(`${DESK}/app/editions/${edition.id}`);
  await page.getByRole("button", { name: "Exhibitor dates", exact: true }).waitFor();
  await part("02-edition-dates", await area("Exhibitor dates"));

  // --- 2. booths ------------------------------------------------------------------------------------
  await page.goto(`${DESK}/app/booths`);
  await page.getByRole("cell", { name: "C01" }).waitFor();
  await view("03-booths");
  await page.getByRole("link", { name: "Add Booth" }).locator("visible=true").first().click();
  await field("Code").fill("C02");
  await field("Hall").fill("Hall C");
  await field("Area").fill("36");
  await field("Price").fill("90000000");
  await view("04-booth-new");

  // --- 3. leads to exhibitor ---------------------------------------------------------------------
  await page.goto(`${DESK}/app/exhibitor-leads`);
  await page.getByText("PT Sinar Garmen Indonesia").locator("visible=true").first().waitFor();
  await view("05-leads");
  await page.goto(`${DESK}/app/exhibitor-leads/board`);
  await page.getByText("PT Indo Rajut Mandiri").locator("visible=true").first().waitFor();
  await view("06-board");

  if (!leads.items.some((l) => l.company_name === "PT Tenun Kreasi Bali")) {
  await page.goto(`${DESK}/app/exhibitor-leads/new`);
  await field("Company Name").fill("PT Tenun Kreasi Bali");
  await field("Contact Name").fill("Made Suardana");
  await field("Email").fill("made@tenunkreasi.example");
  await field("Phone").fill("+62 361 555 123");
  await field("Product Categories").fill("Woven fabric, songket");
  await field("Booth Preference").fill("Corner booth, Hall A");
  await view("07-lead-new");
  await page.getByRole("button", { name: "Save Exhibitor Lead" }).click();
  await page.waitForURL(/\/app\/exhibitor-leads\/[0-9a-f-]{36}/);
  await page.getByRole("heading", { name: "PT Tenun Kreasi Bali" }).waitFor();
  await view("08-lead-page");

  await page.getByRole("link", { name: "Mark Opportunity" }).click();
  await page.getByRole("button", { name: "Move to Opportunity" }).click();
  await page.getByRole("link", { name: "Choose Booth" }).waitFor();
  await page.getByRole("link", { name: "Choose Booth" }).click();
  await page.getByRole("combobox").fill("A0");
  await page.getByRole("option", { name: /^A03/ }).waitFor();
  await view("09-booth-search");
  await page.getByRole("option", { name: /^A03/ }).click();
  await field("Agreed Price").fill("28500000");
  await view("09-choose-booth");
  await page.getByRole("button", { name: "Hold Booth" }).click();
  await page.getByRole("link", { name: "Convert to Exhibitor" }).waitFor();
  await view("10-lead-opportunity");
  await page.getByRole("link", { name: "Convert to Exhibitor" }).click();
  await page.getByRole("button", { name: "Convert to Exhibitor" }).waitFor();
  await view("11-convert");
  await page.getByRole("button", { name: "Convert to Exhibitor" }).click();
  await page.getByRole("link", { name: "Open Exhibitor" }).waitFor();
  await view("12-converted");
  await page.getByRole("link", { name: "Open Exhibitor" }).click();
  await page.getByText("Exhibitor Portal", { exact: true }).locator("visible=true").first().waitFor();
  await part("13-portal-account", await area("Exhibitor Portal"));

  }

  // --- 4. contract and booth payments (PT Maju Tekstil Nusantara) ----------------------------------
  await page.goto(`${DESK}/app/exhibitor-leads/${maju.id}?tab=contract`);
  await page.getByText("Reopen Contract").locator("visible=true").first().waitFor();
  await view("14-contract");
  await page.goto(`${DESK}/app/exhibitor-leads/${maju.id}?tab=payments`);
  await page.getByRole("link", { name: "Record Payment" }).locator("visible=true").first().waitFor();
  await view("15-payments");
  await page.getByRole("link", { name: "Record Payment" }).locator("visible=true").first().click();
  await field("Amount").fill("22500000");
  await field("Reference").fill("Installment 2");
  await view("16-payment-new");
  await page.getByRole("button", { name: "Record Payment" }).click();
  await page.getByRole("button", { name: "Verify Payment" }).waitFor();
  await view("17-payment-review");
  await page.getByRole("button", { name: "Verify Payment" }).click();
  await page.getByText("Payment verified").locator("visible=true").first().waitFor();

  // --- 5. order forms -----------------------------------------------------------------------------
  await page.goto(`${DESK}/app/order-forms`);
  await page.getByRole("heading", { name: "Order Forms" }).waitFor();
  await view("18-forms");
  await page.getByRole("link", { name: "Add Form" }).locator("visible=true").first().click();
  await field("Form Number").fill("12");
  await field("Title").fill("Parking Pass");
  await field("Deadline").fill(day(28));
  await page.getByRole("checkbox", { name: "Catalog of items with prices" }).check();
  await full("19-form-new");
  await page.getByRole("button", { name: "Save Form" }).click();
  await page.waitForURL(/\/app\/order-forms\/[0-9a-f-]{36}/);
  await page.getByRole("link", { name: "Add Item" }).locator("visible=true").first().click();
  await field("Code").fill("12-1");
  await field("Name").fill("Car parking pass");
  await field("Unit").fill("pass");
  await field("Regular").fill("150000");
  await field("Surcharge").fill("200000");
  await field("Onsite").fill("250000");
  await field("Most per Order").fill("5");
  await full("20-item-new");
  await page.getByRole("button", { name: "Save Item", exact: true }).click();
  await page.getByRole("cell", { name: "12-1" }).waitFor();
  await page.getByRole("link", { name: "Import from Excel" }).click();
  await page.getByRole("heading", { name: "Import Catalog" }).waitFor();
  await view("21-import");

  const forms = await staff("GET", `/order-forms?edition_id=${edition.id}`);
  const f04 = (forms.items ?? forms).find((f) => f.code === "04");
  await page.goto(`${DESK}/app/order-forms/${f04.id}`);
  await page.getByRole("cell", { name: "04-3" }).waitFor();
  await view("22-catalog");
  await page.getByRole("cell", { name: "04-3" }).click();
  await page.getByText("Free by Booth Size", { exact: true }).locator("visible=true").first().waitFor();
  await part("23-free", await area("Free by Booth Size"));
  await page.goto(`${DESK}/app/order-forms/${f04.id}`);
  await page.getByRole("tab", { name: "Settings" }).click();
  await page.getByRole("checkbox", { name: "Published to the exhibitor portal" }).waitFor();
  await full("24-settings");
  await page.goto(`${DESK}/app/order-forms/copy`);
  await page.getByRole("heading", { name: "Copy Order Forms" }).waitFor();
  await view("25-copy");

  }

  // --- 6. orders ----------------------------------------------------------------------------------
  await page.goto(`${DESK}/app/exhibitor-orders`);
  await page.getByText("PT Nusantara Fabrics").locator("visible=true").first().waitFor();
  await view("26-orders");
  await page.getByRole("cell", { name: /-O-\d+$/ }).locator("visible=true").first().click();
  await page.getByLabel("Unit price").waitFor();
  await view("27-order");
  await page.getByLabel("Unit price").fill("450000");
  await page.getByRole("button", { name: "Set Price" }).click();
  await page.getByText("Not priced").waitFor({ state: "detached" });
  await page.getByRole("link", { name: "Return to Exhibitor" }).click();
  await page.getByLabel("What should the exhibitor change?").fill("Please send the booth layout with the spotlight positions marked.");
  await view("28-return");
  await page.goBack();

  // The exhibitor signs the contract; then staff approve and take the first payment.
  const portalApi = `${new URL(PORTAL).origin}/api/v1/portal`;
  if ((await portal.request.get(`${portalApi}/auth/me`)).status() !== 200) {
    await portal.goto(`${PORTAL}/login`);
    await portal.getByLabel("Email").fill(SECOND);
    await portal.getByLabel("Password").fill("Guide-Password-2027");
    await portal.getByRole("button", { name: "Sign In" }).click();
    await portal.getByRole("heading", { name: "My Exhibitions" }).waitFor();
  }
  const pcsrf = (await (await portal.request.get(`${portalApi}/auth/me`)).json()).csrf_token;
  const curl = `${portalApi}/exhibitors/${nf.id}/contract`;
  const c = await (await portal.request.get(curl)).json();
  await portal.request.patch(curl, { headers: { "X-CSRF-Token": pcsrf }, data: { pic_name: "Rina Kusuma", company_address: "Jl. Gatot Subroto 45, Jakarta", version: c.version } });
  const c2 = await (await portal.request.get(curl)).json();
  await portal.request.post(`${curl}/signed-copy`, { headers: { "X-CSRF-Token": pcsrf }, multipart: { version: String(c2.version), file: { name: "signed.pdf", mimeType: "application/pdf", buffer: PDF } } });
  await page.reload();
  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByText("approved").locator("visible=true").first().waitFor();
  await view("29-approved");
  await page.getByRole("link", { name: "Record Payment" }).locator("visible=true").first().click();
  await field("Amount").fill("1000000");
  await field("Reference").fill("TRX-0588");
  await view("30-order-payment");
  await page.getByRole("button", { name: "Record Payment" }).click();
  await page.getByRole("button", { name: "Verify Payment" }).click();
  await page.getByText("Payment verified").locator("visible=true").first().waitFor();

  await page.goto(`${DESK}/app/exhibitor-orders?status=APPROVED`);
  await page.getByText("PT Nusantara Fabrics").locator("visible=true").first().waitFor();
  await view("31-orders-approved");
  await page.goto(`${DESK}/app/exhibitor-leads/${maju.id}?tab=orders`);
  await page.getByText("Forms:", { exact: false }).locator("visible=true").first().waitFor();
  await view("32-lead-orders");
  await page.goto(`${DESK}/app`);
  await page.getByText("Service orders").waitFor();
  await view("33-overview-after");
  console.log("done");
} catch (e) {
  console.log(`FAIL ${String(e).split("\n")[0]}`);
  await page.screenshot({ path: `${OUT}/failed.png`, fullPage: true }).catch(() => {});
  process.exitCode = 1;
} finally {
  await browser.close();
}
