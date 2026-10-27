// Public campaign form against the running stack: a link on an Active edition, the form in
// both languages, required fields, a registration with UTM tags, and a closed link.
//   EMS_URL=http://localhost:8080 EMS_CAMPAIGN_URL=http://localhost:5175 \
//   EMS_EMAIL=... EMS_PASSWORD=... CHROMIUM=/snap/bin/chromium node e2e/form.mjs
import { chromium, request } from "playwright-core";

const API = process.env.EMS_URL ?? "http://localhost:8080";
const FORM = process.env.EMS_CAMPAIGN_URL ?? "http://localhost:5175";
const run = Date.now().toString(36);

function check(ok, what) {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) process.exitCode = 1;
}

// Desk side: an admin makes a link on the first Active edition.
const desk = await request.newContext({ baseURL: API });
const login = await desk.post("/api/v1/auth/login", { data: { email: process.env.EMS_EMAIL, password: process.env.EMS_PASSWORD } });
if (!login.ok()) throw new Error(`login failed: ${login.status()}`);
const headers = { "X-CSRF-Token": (await login.json()).csrf_token };
const editions = await (await desk.get("/api/v1/editions?page_size=100")).json();
const edition = (editions.items ?? editions).find((e) => e.status === "ACTIVE");
if (!edition) throw new Error("No Active edition; set one to Active first.");
const make = async (data) => (await desk.post("/api/v1/campaign-links", { headers, data: { edition_id: edition.id, ...data } })).json();
const link = await make({ name: `E2E form ${run}` });
const closed = await make({ name: `E2E closed ${run}`, is_active: false });

// Visitor side: a fresh browser, no EMS session.
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, locale: "en-US" });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

try {
  await page.goto(`${FORM}/r/${link.token}?utm_source=e2e&utm_medium=test&gclid=ignored`);
  await page.getByRole("heading", { name: edition.name }).waitFor();
  check(true, "form shows the edition");

  await page.getByRole("button", { name: "Register" }).click();
  check(await page.getByText("Enter your email or phone number.").first().isVisible(), "email or phone is required");
  check(await page.getByText("Tick the box to agree.").isVisible(), "consent is required");

  await page.getByRole("button", { name: "Ganti ke Bahasa Indonesia" }).click();
  check(await page.getByRole("button", { name: "Daftar" }).isVisible(), "switches to Indonesian");

  await page.getByLabel("Nama Lengkap").fill(`E2E Visitor ${run}`);
  await page.getByLabel("Email").fill(`campaign-${run}@example.test`);
  await page.getByRole("checkbox").last().check();
  // The server rejects forms sent faster than a person can fill them.
  await page.waitForTimeout(3500);
  await page.getByRole("button", { name: "Daftar" }).click();
  await page.getByRole("heading", { name: "Terima kasih" }).waitFor();
  check(true, "registration accepted");

  const leads = await (await desk.get(`/api/v1/visitor-leads?edition_id=${edition.id}&campaign_link_id=${link.id}`)).json();
  const lead = leads.items[0];
  check(leads.total === 1 && lead.email === `campaign-${run}@example.test`, "lead is in the edition with its campaign");
  const detail = await (await desk.get(`/api/v1/visitor-leads/${lead.id}`)).json();
  check(detail.utm_source === "e2e" && detail.utm_medium === "test", "UTM tags kept, other parameters ignored");
  check(detail.lead_owner_id === null && detail.qr_status === "ACTIVE", "registered, not assigned");

  await page.goto(`${FORM}/r/${closed.token}`);
  await page.getByRole("heading", { name: /closed|ditutup/ }).waitFor();
  check(true, "inactive link shows the closed page");
  check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
} finally {
  await browser.close();
  await desk.dispose();
}
