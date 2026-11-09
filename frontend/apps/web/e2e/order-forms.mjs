// Order form setup click-through (docs/EXHIBITOR_ORDER_FORMS.md Phase 2): add a form, add an item,
// import the catalog template, upload an item picture, publish, open Copy from Edition.
// Runs in the edition the desk opens on. Uses a locally installed Chromium (no browser download).
//   EMS_URL=http://localhost:5173 EMS_EMAIL=... EMS_PASSWORD=... CHROMIUM=/snap/bin/chromium \
//   OUT=/tmp/order-forms node e2e/order-forms.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.env.EMS_URL ?? "http://localhost:5173";
const OUT = process.env.OUT ?? "order-forms-out";
mkdirSync(OUT, { recursive: true });

// 1x1 PNG.
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);
// A fresh form number each run, so reruns do not collide: "9" + digit + letter.
const CODE = `9${Math.floor(Math.random() * 10)}${"abcdefghijklmnopqrstuvwxyz"[Math.floor(Math.random() * 26)]}`;

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
const page = await ctx.newPage();
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));
const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
const step = (text) => console.log(`- ${text}`);
// Labels start with the field name; required fields add a hidden "(required)".
const field = (label) => page.getByLabel(new RegExp(`^${label}\\b`));

await page.goto(`${BASE}/login`);
await page.getByLabel("Email").fill(process.env.EMS_EMAIL);
await page.getByLabel("Password").fill(process.env.EMS_PASSWORD);
await page.getByRole("button", { name: "Sign In" }).click();
await page.waitForURL((u) => !u.pathname.startsWith("/login"));

await page.goto(`${BASE}/app/order-forms`);
await page.getByRole("heading", { name: "Order Forms" }).waitFor();
await shot("01-list");
step("list opens");

await page.getByRole("link", { name: "Add Form" }).first().click();
await field("Form Number").fill(CODE);
await field("Title").fill(`E2E Electrical ${CODE}`);
await field("Deadline").fill("2027-02-23");
await page.getByRole("button", { name: "Save Form" }).click();
await page.waitForURL(/\/app\/order-forms\/[0-9a-f-]{36}/);
await page.getByText(`${CODE} · E2E Electrical ${CODE}`).waitFor();
step(`form ${CODE} added`);

await page.getByRole("link", { name: "Add Item" }).first().click();
await field("Code").fill("L-001");
await field("Name").fill("Spotlight 100 W");
await field("Section").fill("A. Lighting & Equipment");
await field("Regular").fill("1046500");
await field("Surcharge").fill("1151150");
await page.getByRole("button", { name: "Save Item", exact: true }).click();
await page.getByRole("cell", { name: "L-001" }).waitFor();
step("item added");

await page.getByRole("link", { name: "Import from Excel" }).click();
const template = await page.request.get(`${BASE}/api/v1/order-forms/item-import-template`);
if (!template.ok()) throw new Error(`template ${template.status()}`);
await field("Catalog").setInputFiles({
  name: "catalog.xlsx",
  mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  buffer: Buffer.from(await template.body()),
});
await page.getByRole("button", { name: "Import", exact: true }).click();
await page.getByText("1 items added and 0 updated.").waitFor();
await shot("02-import");
step("template imported");

await page.getByRole("link", { name: "Back to Catalog" }).click();
await page.getByRole("cell", { name: "E-001" }).waitFor();
await page.getByRole("cell", { name: "L-001" }).click();
await field("Picture").setInputFiles({ name: "spot.png", mimeType: "image/png", buffer: PNG });
await page.getByRole("button", { name: "Upload Picture" }).click();
await page.getByRole("img", { name: "Spotlight 100 W" }).waitFor();
await shot("03-item");
step("picture uploaded");

await page.getByRole("link", { name: `Form ${CODE}` }).click();
await page.getByRole("tab", { name: "Settings" }).click();
await page.getByRole("checkbox", { name: "Published to the exhibitor portal" }).click();
await page.getByRole("button", { name: "Save Form" }).click();
await page.getByText("Published", { exact: true }).first().waitFor();
await shot("04-settings");
await page.getByRole("tab", { name: "Catalog" }).click();
await page.getByText("2 active of 2 items").waitFor();
await shot("05-catalog");
step("form published");

await page.goto(`${BASE}/app/order-forms/copy`);
await page.getByRole("heading", { name: "Copy Order Forms" }).waitFor();
await shot("06-copy");
step("copy page opens");

await browser.close();
if (errors.length) {
  console.log(`console errors:\n${errors.join("\n")}`);
  process.exit(1);
}
console.log(`order form setup flow passed (form ${CODE})`);
