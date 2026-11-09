// Exhibitor order forms in the portal (docs/EXHIBITOR_ORDER_FORMS.md Phase 3).
// Setup through the desk API in a fresh test edition whose price periods cover today: form with a
// catalog, extra items and a fitting-location attachment, booth, lead, Convert. Then the portal UI:
// invitation, Order Forms list, fill quantities and an extra item, save the draft, attach a file,
// review, send, and see the sent order.
//   EMS_URL=http://localhost:5173 PORTAL_URL=http://localhost:5176/exhibitor EMS_EMAIL=... \
//   EMS_PASSWORD=... CHROMIUM=/snap/bin/chromium node e2e/order-forms.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const DESK = process.env.EMS_URL ?? "http://localhost:5173";
const PORTAL = (process.env.PORTAL_URL ?? "http://localhost:5176/exhibitor").replace(/\/$/, "");
const OUT = process.env.OUT ?? "e2e-out/order-forms";
mkdirSync(OUT, { recursive: true });
const run = Date.now().toString(36).toUpperCase();
const PDF = Buffer.from("%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n");

function check(ok, what) {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) process.exitCode = 1;
}

const day = (offset) => new Date(Date.now() + offset * 86_400_000).toISOString().slice(0, 10);

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const desk = await (await browser.newContext()).newPage();
const portal = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const errors = [];
portal.on("pageerror", (e) => errors.push(String(e)));
// API refusals (the 401 session check, the 422 this flow provokes) show in the page; script errors count.
portal.on("console", (m) => m.type() === "error" && !m.text().startsWith("Failed to load resource") && errors.push(m.text()));
const shot = (name) => portal.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });

let csrf = "";
async function staff(method, path, body, retried = false) {
  const r = await desk.request.fetch(`${DESK}/api/v1${path}`, {
    method,
    headers: { "X-CSRF-Token": csrf },
    data: body,
  });
  // The API commits after the response is sent (get_session runs as a request-scoped
  // dependency), so a record created a moment ago can still be invisible. Retry once.
  if (r.status() === 404 && !retried) {
    await desk.waitForTimeout(300);
    return staff(method, path, body, true);
  }
  if (!r.ok()) throw new Error(`${method} ${path}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
}

try {
  // --- desk setup through the API -------------------------------------------------------
  await desk.goto(`${DESK}/login`);
  await desk.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await desk.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await desk.getByRole("button", { name: "Sign In" }).click();
  await desk.waitForURL(/\/app/);
  csrf = (await staff("GET", "/auth/me")).csrf_token;

  const exhibition = await staff("POST", "/exhibitions", { code: `E2EOF${run}`.slice(0, 20), name: `E2E Order Forms ${run}` });
  const edition = await staff("POST", "/editions", {
    exhibition_id: exhibition.id,
    year: 2027,
    start_date: day(40),
    end_date: day(43),
    timezone: "Asia/Jakarta",
    default_currency: "IDR",
    price_regular_from: day(-5),
    price_regular_to: day(20),
    price_surcharge_from: day(21),
    price_surcharge_to: day(39),
    price_onsite_from: day(40),
    price_onsite_to: day(43),
  });
  const form = await staff("POST", "/order-forms", {
    edition_id: edition.id,
    code: "04",
    title: "Electrical Fittings & Supplies",
    has_catalog: true,
    allow_custom_items: true,
    attachment_purposes: ["FITTING_LOCATION"],
    deadline_on: day(14),
    instructions: "Orders are non-refundable after the deadline.",
  });
  await staff("POST", `/order-forms/${form.id}/items`, { section: "A. Lighting & Equipment", code: "E-001", name: "Fluorescent lamp", size: "40 W", price_regular: "740600" });
  await staff("POST", `/order-forms/${form.id}/items`, { section: "A. Lighting & Equipment", code: "E-002", name: "Spotlight", size: "100 W", price_regular: "1046500", max_quantity: 5 });
  await staff("POST", `/order-forms/${form.id}/items`, { section: "B. Electricity Power", code: "P-001", name: "Power 2 A", price_regular: "1014300" });
  await staff("PATCH", `/order-forms/${form.id}`, { is_published: true, version: form.version });
  // A questions-only form: badges for the stand staff.
  await staff("POST", "/order-forms", { edition_id: edition.id, code: "09", title: "Exhibitor Badges & Visa", details_type: "badges_visa", is_published: true, sort_order: 9 });
  const booth = await staff("POST", "/booths", { edition_id: edition.id, code: "A01", area_sqm: "18", price: "30000000" });
  let lead = await staff("POST", "/exhibitor-leads", { edition_id: edition.id, company_name: `E2E Exhibitor ${run}`, contact_name: "E2E Contact", email: `orders-${run.toLowerCase()}@example.test` });
  lead = await staff("POST", `/exhibitor-leads/${lead.id}/stage`, { stage: "OPPORTUNITY", version: lead.version });
  lead = await staff("PUT", `/exhibitor-leads/${lead.id}/booth`, { booth_id: booth.id, version: lead.version });
  const converted = await staff("POST", `/exhibitor-leads/${lead.id}/convert`, { version: lead.version });
  check(Boolean(converted.invitation?.url), "test edition, published form, and converted exhibitor ready");

  // --- portal ---------------------------------------------------------------------------
  const invite = new URL(converted.invitation.url);
  await portal.goto(`${PORTAL}${invite.pathname.replace(/^\/exhibitor/, "")}${invite.search}`);
  await portal.getByLabel("New Password", { exact: false }).first().fill("e2e-portal-Password-1");
  await portal.getByLabel("Confirm Password", { exact: false }).fill("e2e-portal-Password-1");
  await portal.getByRole("button", { name: /Set Password/ }).click();
  await portal.getByText(edition.code).first().click();
  await portal.getByRole("button", { name: "Open Order Forms" }).click();
  await portal.getByRole("heading", { name: "Order Forms" }).waitFor();
  await portal.getByText("0 of 2 done").waitFor();
  await shot("01-forms");
  check(true, "Order Forms list opens from the exhibition page");

  await portal.getByRole("link", { name: /Electrical Fittings/ }).click();
  await portal.getByRole("heading", { name: /04 · Electrical Fittings/ }).waitFor();
  await portal.getByLabel("Quantity of Fluorescent lamp").fill("3");
  await portal.getByLabel("Quantity of Spotlight").fill("6");
  await portal.getByText("Total IDR 8,500,800").waitFor();
  await portal.getByRole("button", { name: "Add Extra Item" }).click();
  await portal.getByLabel("Extra item 1", { exact: true }).fill("LED strip, warm white");
  await portal.getByLabel("Size", { exact: true }).fill("5 m");
  await portal.getByRole("button", { name: "Save Draft" }).click();
  await portal.getByText("At most 5 per order.").waitFor();
  check(true, "a quantity over the item's limit is refused with the reason");

  await portal.getByLabel("Quantity of Spotlight").fill("2");
  await portal.getByRole("button", { name: "Save Draft" }).click();
  await portal.getByText("Draft saved.", { exact: false }).waitFor();
  await portal.getByLabel("Add Fitting Location").setInputFiles({ name: "booth-layout.pdf", mimeType: "application/pdf", buffer: PDF });
  await portal.getByRole("button", { name: "Upload", exact: true }).last().click();
  await portal.getByRole("button", { name: "booth-layout.pdf", exact: true }).waitFor();
  await shot("02-draft");
  check(true, "draft saved with an extra item and an attachment");

  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByRole("heading", { name: /Review Order/ }).waitFor();
  await portal.getByText("Total IDR 4,314,800").waitFor();
  await portal.getByText("Extra items are priced by the organizer", { exact: false }).waitFor();
  await shot("03-review");
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText(`Order ${edition.code}-O-0001 sent.`, { exact: false }).waitFor();
  await portal.getByText("The organizer confirms this order once your booth contract is signed.").waitFor();
  await shot("04-sent");
  check(true, "order sent with a number, waiting for the signed contract");
  await portal.getByRole("button", { name: "Order More" }).waitFor();
  check((await portal.getByLabel("Quantity of Fluorescent lamp").count()) === 0, "after sending, a new order starts only with Order More");
  await portal.getByRole("button", { name: "Order More" }).click();
  await portal.getByLabel("Quantity of Fluorescent lamp").waitFor();

  // --- a questions form ---------------------------------------------------------------------
  await portal.goto(`${PORTAL}/e/${lead.id}/forms/09`);
  await portal.getByRole("heading", { name: /09 · Exhibitor Badges/ }).waitFor();
  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText("Some answers are missing.", { exact: false }).waitFor();
  check(true, "questions: sending with missing answers is refused with the reasons");
  await portal.goto(`${PORTAL}/e/${lead.id}/forms/09`);
  await portal.getByLabel("Indonesian company").check();
  await portal.getByRole("button", { name: "Add Badge" }).click();
  await portal.getByLabel("Full name 1").fill("Budi Santoso");
  await portal.getByLabel("Gender 1").selectOption("MALE");
  await portal.getByLabel("Designation 1").fill("Sales Manager");
  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByText("Your Answers", { exact: true }).waitFor();
  await shot("05-questions-review");
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText(`Order ${edition.code}-O-0002 sent.`, { exact: false }).waitFor();
  check(true, "questions: badge holders answered and sent");
  await portal.goto(`${PORTAL}/e/${lead.id}/forms/04`);

  // --- desk review ------------------------------------------------------------------------
  const deskShot = (name) => desk.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await desk.setViewportSize({ width: 1440, height: 900 });
  await desk.evaluate((id) => localStorage.setItem("ems.edition", id), edition.id);
  await desk.goto(`${DESK}/app/exhibitor-orders`);
  await desk.getByRole("cell", { name: `${edition.code}-O-0001` }).click();
  await desk.getByRole("heading", { name: `Order ${edition.code}-O-0001` }).waitFor();
  check(await desk.getByRole("button", { name: "Approve" }).isDisabled(), "desk: Approve waits for the extra item price and the contract");
  await desk.getByLabel("Unit price").fill("250000");
  await desk.getByRole("button", { name: "Set Price" }).click();
  await desk.getByText("Total IDR 4,564,800").waitFor();
  await deskShot("06-desk-order");
  check(true, "desk: extra item priced, total updated");

  await desk.getByRole("link", { name: "Return to Exhibitor" }).click();
  await desk.getByLabel("What should the exhibitor change?").fill("Please add the power outlet for the spotlights.");
  await desk.getByRole("button", { name: "Return to Exhibitor" }).click();
  await desk.getByRole("heading", { name: `Order ${edition.code}-O-0001` }).waitFor();
  check(true, "desk: order returned with a reason");

  await portal.reload();
  await portal.getByText("Please add the power outlet for the spotlights.", { exact: false }).waitFor();
  await portal.getByLabel("Quantity of Power 2 A").fill("1");
  await portal.getByRole("button", { name: "Review and Send" }).click();
  await portal.getByRole("button", { name: "Send Order" }).click();
  await portal.getByText(`Order ${edition.code}-O-0001 sent.`, { exact: false }).waitFor();
  check(true, "portal: returned order changed and sent again with the same number");

  // Sign the contract through the portal API, then approve in the desk.
  const portalApi = `${new URL(PORTAL).origin}/api/v1/portal`;
  const portalCsrf = (await (await portal.request.get(`${portalApi}/auth/me`)).json()).csrf_token;
  const contractUrl = `${portalApi}/exhibitors/${lead.id}/contract`;
  const contract = await (await portal.request.get(contractUrl)).json();
  await portal.request.patch(contractUrl, { headers: { "X-CSRF-Token": portalCsrf }, data: { pic_name: "E2E PIC", company_address: "Jl. E2E 1, Jakarta", version: contract.version } });
  const filled = await (await portal.request.get(contractUrl)).json();
  const signed = await portal.request.post(`${contractUrl}/signed-copy`, {
    headers: { "X-CSRF-Token": portalCsrf },
    multipart: { version: String(filled.version), file: { name: "signed.pdf", mimeType: "application/pdf", buffer: PDF } },
  });
  check(signed.ok(), "contract signed");
  await desk.reload();
  // The extra item kept its staff price: the exhibitor sent it back unchanged.
  await desk.getByText("Total IDR 5,579,100").waitFor();
  await desk.getByRole("button", { name: "Approve" }).click();
  await desk.getByText(`Order ${edition.code}-O-0001 approved`).waitFor();
  await deskShot("07-desk-approved");
  check(true, "desk: order approved once priced and the contract signed");

  await desk.goto(`${DESK}/app/exhibitor-leads/${lead.id}?tab=orders`);
  await desk.getByText("Forms: 2 of 2 done").waitFor();
  await deskShot("08-lead-orders-tab");
  check(true, "desk: the lead's Orders tab shows the progress and the order");

  await portal.goto(`${PORTAL}/e/${lead.id}/forms/04`);
  await portal.getByText("Approved", { exact: true }).first().waitFor();
  check(true, "portal: the exhibitor sees the order approved");

  await portal.getByRole("link", { name: "Order Forms" }).first().click();
  await portal.getByText("2 of 2 done").waitFor();
  await portal.setViewportSize({ width: 390, height: 844 });
  await shot("05-forms-mobile");
  check(
    await portal.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
    "no horizontal page scroll on a phone",
  );
} catch (e) {
  check(false, String(e).split("\n")[0]);
  await shot("failed").catch(() => {});
} finally {
  await browser.close();
}
check(errors.length === 0, `no portal console errors${errors.length ? `: ${errors.join(" | ")}` : ""}`);
