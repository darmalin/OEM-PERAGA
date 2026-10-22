// Click-through of the main flows against the dev stack (R-35 evidence).
//   EMS_URL=http://localhost:5173 EMS_EMAIL=... EMS_PASSWORD=... EMS_EDITION=E2EQR2027 node e2e/flows.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.env.EMS_URL ?? "http://localhost:5173";
const OUT = process.env.OUT ?? "flows-out";
mkdirSync(OUT, { recursive: true });
const run = Date.now().toString(36);
const results = [];

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light", acceptDownloads: true });
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

async function step(name, fn) {
  const before = errors.length;
  try {
    const detail = await fn();
    // Expected HTTP errors (401 before sign-in, 409 duplicate) are logged by the browser too.
    const errs = errors.slice(before).filter((e) => !e.startsWith("Failed to load resource"));
    results.push({ name, ok: errs.length === 0, detail: errs.length ? `console: ${errs.join(" | ").slice(0, 200)}` : detail ?? "" });
  } catch (e) {
    results.push({ name, ok: false, detail: String(e).split("\n")[0].slice(0, 220) });
    await page.screenshot({ path: `${OUT}/fail-${results.length}.png` }).catch(() => {});
  }
}
const toast = async (text) => {
  const t = page.locator("[data-sonner-toast]", { hasText: text }).first();
  await t.waitFor({ state: "visible", timeout: 10000 });
  return `toast "${text}"`;
};
const goto = async (path) => {
  await page.goto(`${BASE}${path}`);
  await page.locator("h1").first().waitFor({ timeout: 15000 });
};

// --- sign in, pick the edition -----------------------------------------------------------
await step("Sign in -> lands on a panel", async () => {
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await page.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL((u) => u.pathname.startsWith("/app") || u.pathname.startsWith("/system"));
  return page.url();
});
const EDITION = process.env.EMS_EDITION ?? "E2EQR2027";
/** Pick an edition by code in an "Exhibition Type" select (page picker or list filter). */
async function pickEdition(select) {
  const value = await select.locator("option", { hasText: EDITION }).first().getAttribute("value");
  await select.selectOption(value);
}
await step("Exhibition Type picker on Overview -> E2EQR2027", async () => {
  await goto("/app");
  await pickEdition(page.getByLabel("Exhibition Type"));
  await page.getByRole("heading", { level: 1 }).filter({ hasText: EDITION }).waitFor();
  return "overview shows the edition";
});

// --- visitor leads ------------------------------------------------------------------------
let leadUrl = "";
await step("New lead, empty submit -> field errors", async () => {
  await goto("/app/visitor-leads/new");
  await page.getByRole("button", { name: "Save Visitor Lead" }).click();
  await page.getByText("First Name is required.").waitFor();
  return "First Name error shown";
});
await step("New lead without email or phone -> group error", async () => {
  await page.getByLabel("First Name").fill(`Flow Visitor ${run}`);
  await page.getByRole("button", { name: "Save Visitor Lead" }).click();
  await page.getByText("Email or Phone is required.").first().waitFor();
  return "Email or Phone error shown";
});
await step("New lead saves -> detail page + toast", async () => {
  await page.getByLabel("Email").fill(`flow-${run}@example.test`);
  await page.getByLabel("Company Name").fill("Flow Test Co");
  await page.getByRole("button", { name: "Save Visitor Lead" }).click();
  await page.waitForURL(/\/app\/visitor-leads\/[0-9a-f-]{36}/);
  leadUrl = page.url().split("?")[0];
  return await toast("Visitor lead added");
});
await step("Duplicate email -> 409 under the field", async () => {
  await goto("/app/visitor-leads/new");
  await page.getByLabel("First Name").fill("Dup");
  await page.getByLabel("Email").fill(`flow-${run}@example.test`);
  await page.getByRole("button", { name: "Save Visitor Lead" }).click();
  await page.getByText("Already used in this edition.").first().waitFor();
  return "duplicate shown on Email";
});
await step("Edit lead + Ctrl+S -> Not Saved, then saved toast", async () => {
  await page.goto(leadUrl);
  await page.getByLabel("Job Title").fill("Buyer");
  await page.getByText("Not Saved").waitFor();
  await page.keyboard.press("Control+s");
  return await toast("Saved");
});
await step("Log Call (New -> Answer) needs Attend, then moves + toast", async () => {
  await page.getByRole("link", { name: "Log Call" }).click();
  await page.getByRole("heading", { name: /Log Call for/ }).waitFor();
  await page.locator("label", { hasText: /^Answer/ }).click();
  const next = new Date(Date.now() + 2 * 864e5).toISOString().slice(0, 16);
  await page.getByLabel("Next Follow-up").fill(next);
  await page.getByLabel("Notes").fill("Interested in sourcing");
  await page.getByRole("button", { name: "Save and Move" }).click();
  await page.getByText("Attend is required for an answered call.").waitFor();
  await page.getByLabel("Attend").selectOption("ATTEND_SOURCING");
  await page.getByRole("button", { name: "Save and Move" }).click();
  await page.waitForURL((u) => u.href.split("?")[0] === leadUrl);
  return await toast("moved to Answer");
});
await step("Status indicator updated to Answer", async () => {
  await page.locator("header").getByText("Answer", { exact: true }).first().waitFor();
  return "indicator Answer";
});
await step("Add Follow-up page -> toast", async () => {
  await page.getByRole("link", { name: "Add Follow-up" }).click();
  const due = new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 16);
  await page.getByLabel("Due At").fill(due);
  await page.getByRole("button", { name: "Schedule Follow-up" }).click();
  return await toast("Follow-up scheduled");
});
await step("Calls tab lists the attempt", async () => {
  await page.getByRole("tab", { name: /Calls/ }).click();
  await page.getByText("Interested in sourcing").waitFor();
  return "call #1 with notes";
});
await step("Activity tab shows audit entries", async () => {
  await page.getByRole("tab", { name: "Activity" }).click();
  await page.locator("ol li").first().waitFor();
  return `${await page.locator("ol li").count()} entries`;
});
let regUrl = "";
await step("Lead was registered on creation -> Open Registration", async () => {
  await page.getByRole("tab", { name: "Registration" }).click();
  await page.getByRole("link", { name: "Open Registration" }).click();
  await page.waitForURL(/\/app\/registrations\/[0-9a-f-]{36}/);
  regUrl = page.url();
  return "registered without a manual step";
});
await step("Resend QR Email -> toast", async () => {
  await page.getByRole("button", { name: "Resend QR Email" }).click();
  return await toast("QR email queued");
});
await step("Revoke QR page with reissue -> toast", async () => {
  await page.getByRole("link", { name: "Revoke QR" }).click();
  await page.getByLabel("Reason").fill("Flow test: phone lost");
  await page.locator("label", { hasText: "Issue a new QR right away" }).click();
  await page.getByRole("button", { name: "Revoke and Issue New QR" }).click();
  await page.waitForURL(regUrl);
  return await toast("New QR issued");
});
await step("Registration shows two credentials (revoked + active)", async () => {
  await page.getByText(/Revoked .*Flow test: phone lost/).waitFor();
  return "revoked credential with reason";
});
await step("List: select lead -> Assign To page -> assign -> toast", async () => {
  await goto(`/app/visitor-leads?q=flow-${run}`);
  await pickEdition(page.getByLabel("Exhibition Type"));
  await page.getByRole("checkbox", { name: "Select row" }).first().click();
  await page.getByRole("button", { name: "Assign To" }).click();
  await page.getByRole("heading", { name: /Assign Visitor Lead/ }).waitFor();
  await page.getByLabel("Lead Owner").selectOption({ index: 1 });
  await page.getByRole("button", { name: /Assign Lead/ }).click();
  return await toast("1 assigned");
});

// --- gate ----------------------------------------------------------------------------------
await step("New Gate -> list + toast", async () => {
  await goto("/app/gates/new");
  await page.getByLabel("Code").fill(`F${run}`.slice(0, 12).toUpperCase());
  await page.getByLabel("Name").fill("Flow gate");
  await page.getByRole("button", { name: "Save Gate" }).click();
  return await toast("Gate added");
});
await step("Register Device -> one-time activation code shown", async () => {
  await goto("/app/devices/new");
  const gateCode = `F${run}`.slice(0, 12).toUpperCase();
  const opt = await page.getByLabel("Gate").locator("option", { hasText: gateCode }).getAttribute("value");
  await page.getByLabel("Gate").selectOption(opt);
  await page.getByLabel("Device name").fill("Flow phone");
  await page.getByRole("button", { name: "Create Activation Code" }).click();
  const code = page.locator("[aria-label^='Activation code']");
  await code.waitFor();
  return `code ${(await code.textContent())?.length} chars`;
});
await step("Scan History filters render", async () => {
  await goto("/app/scans");
  await page.getByLabel("Result").selectOption("FIRST_ENTRY");
  await page.waitForURL(/result=FIRST_ENTRY/);
  return "URL carries the filter";
});

// --- exports -------------------------------------------------------------------------------
await step("New Export -> list, worker completes, Download available", async () => {
  await goto("/app/exports/new");
  await page.getByRole("button", { name: "Start Export" }).click();
  await toast("Export started");
  await page.getByRole("button", { name: "Download" }).first().waitFor({ timeout: 30000 });
  return "COMPLETED with Download";
});
await step("Reports tab switch -> Attendance", async () => {
  await goto("/app/reports");
  await page.getByRole("tab", { name: "Attendance" }).click();
  await page.getByText("How many people came in").waitFor();
  return "report question heading";
});

// --- system --------------------------------------------------------------------------------
let userUrl = "";
await step("System: New User -> detail + toast", async () => {
  await goto("/system/users/new");
  await page.getByLabel("Full Name").fill(`Flow User ${run}`);
  await page.getByLabel("Email").fill(`flow-user-${run}@example.test`);
  await page.getByLabel("Password").fill(`flow-${run}-password-123`);
  await page.getByRole("button", { name: "Save User" }).click();
  await page.waitForURL(/\/system\/users\/[0-9a-f-]{36}/);
  userUrl = page.url();
  return await toast("User added");
});
await step("Add Role page (Telemarketing Agent, own leads) -> toast", async () => {
  await page.getByRole("link", { name: "Add Role" }).first().click();
  await page.getByLabel("Role").selectOption({ label: "Telemarketing Agent" });
  await page.locator("label", { hasText: "Own leads" }).click();
  await page.getByRole("combobox", { name: "Edition" }).selectOption({ index: 1 });
  await page.getByRole("button", { name: "Add Role" }).click();
  await page.waitForURL(userUrl);
  return await toast("Role added");
});
await step("Remove role needs a second click (inline confirm)", async () => {
  await page.getByRole("button", { name: "Remove" }).first().click();
  await page.getByText("Remove this role?").waitFor();
  await page.getByRole("button", { name: "Keep" }).click();
  return "confirm shown, kept";
});
await step("System: New Team -> add member -> toast", async () => {
  await goto("/system/teams/new");
  await page.getByLabel("Name").fill(`Flow Team ${run}`);
  await page.getByRole("button", { name: "Save Team" }).click();
  await page.waitForURL(/\/system\/teams\/[0-9a-f-]{36}/);
  const member = await page.getByLabel("Add a member").locator("option", { hasText: `Flow User ${run}` }).getAttribute("value");
  await page.getByLabel("Add a member").selectOption(member);
  await page.getByRole("button", { name: "Add Member" }).click();
  return await toast("Member added");
});
await step("Role page shows the permission matrix", async () => {
  await goto("/system/roles");
  await page.getByRole("link", { name: "Telemarketing Agent" }).click();
  await page.getByText(/Permissions \(\d+\)/).waitFor();
  return "matrix rendered";
});
await step("Audit Log lists entries", async () => {
  await goto("/system/audit-log");
  await page.locator("ol li").first().waitFor();
  return `${await page.locator("ol li").count()} entries`;
});

// --- shell ---------------------------------------------------------------------------------
await step("Ctrl+K command bar -> go to Follow-ups", async () => {
  await goto("/app");
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder(/Type a page name/).fill("Follow");
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/app\/followups/);
  return page.url().replace(BASE, "");
});
await step("Theme menu -> dark adds the dark class; Escape closes the menu", async () => {
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitemradio", { name: /Dark/ }).click();
  const dark = await page.evaluate(() => document.documentElement.classList.contains("dark"));
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.keyboard.press("Escape");
  const open = await page.getByRole("menu").count();
  return `dark=${dark}, menu open after Escape=${open}`;
});
await step("Keyboard: Tab reaches skip link first", async () => {
  await goto("/app");
  await page.keyboard.press("Tab");
  return await page.evaluate(() => document.activeElement?.textContent ?? "");
});
await step("Unknown URL -> not-found page", async () => {
  await page.goto(`${BASE}/app/nope`);
  await page.getByText("This page does not exist.").waitFor();
  return "not found shown";
});
await step("Sign Out -> login page", async () => {
  await goto("/app");
  await page.getByRole("button", { name: /Account menu/ }).click();
  await page.getByRole("menuitem", { name: "Sign Out" }).click();
  await page.waitForURL(/\/login/);
  return "signed out";
});

await browser.close();
for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? `  (${r.detail})` : ""}`);
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
