// Smoke test: sign in, open every page in both panels, record console errors and screenshots.
// Uses a locally installed Chromium (no browser download).
//   EMS_URL=http://localhost:5173 EMS_EMAIL=... EMS_PASSWORD=... CHROMIUM=/snap/bin/chromium \
//   OUT=/tmp/smoke node e2e/smoke.mjs
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const BASE = process.env.EMS_URL ?? "http://localhost:5173";
const OUT = process.env.OUT ?? "smoke-out";
mkdirSync(OUT, { recursive: true });

export const PAGES = [
  "/app", "/app/visitor-leads", "/app/visitor-leads/board", "/app/visitor-leads/new", "/app/visitor-leads/assign", "/app/my-calls",
  "/app/followups", "/app/registrations", "/app/imports", "/app/imports/new", "/app/exports",
  "/app/exports/new", "/app/gates", "/app/gates/new", "/app/devices", "/app/devices/new", "/app/scans",
  "/app/reconciliation", "/app/overrides/new", "/app/reports", "/app/dashboard", "/app/dashboard?tab=daily", "/app/dashboard?tab=user", "/app/dashboard?tab=email", "/app/exhibitions", "/app/exhibitions/new",
  "/app/editions", "/app/editions/new", "/app/venues", "/app/venues/new", "/app/custom-fields",
  "/app/custom-fields/new", "/app/field-options", "/app/field-options/new", "/app/lead-sources", "/app/lead-sources/new", "/system", "/system/users",
  "/system/users/new", "/system/roles", "/system/roles/new", "/system/teams", "/system/teams/new",
  "/system/audit-log", "/system/email-templates", "/system/email-templates/new", "/system/email-accounts", "/system/email-accounts/new", "/system/email-log",
];

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const results = [];
for (const [name, viewport, scheme] of [
  ["desktop-light", { width: 1440, height: 900 }, "light"],
  ["desktop-dark", { width: 1440, height: 900 }, "dark"],
  ["mobile-light", { width: 375, height: 812 }, "light"],
]) {
  const ctx = await browser.newContext({ viewport, colorScheme: scheme, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${BASE}/login`);
  await page.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await page.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  for (const path of PAGES) {
    const before = errors.length;
    await page.goto(`${BASE}${path}`);
    await page.locator("h1").first().waitFor({ timeout: 15000 }).catch(() => {});
    await page.waitForLoadState("networkidle").catch(() => {});
    const h1 = (await page.locator("h1").first().textContent().catch(() => null)) ?? "(no h1)";
    const body = await page.locator("body").innerText();
    // Horizontal overflow of the page itself (R-03); inner table scroll is allowed.
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    const broken = /Could not load this page|This page does not exist|Something went wrong/.test(body);
    results.push({ mode: name, path, h1: h1.trim(), broken, overflow, errors: errors.slice(before) });
    await page.screenshot({ path: `${OUT}/${name}${path.replaceAll("/", "_")}.png`, fullPage: false });
  }
  await ctx.close();
}
await browser.close();
const bad = results.filter((r) => r.broken || r.overflow || r.errors.length);
for (const r of results) console.log(`${r.mode.padEnd(14)} ${r.path.padEnd(32)} ${r.h1}${r.broken ? "  BROKEN" : ""}${r.overflow ? "  OVERFLOW" : ""}${r.errors.length ? `  ERRORS ${JSON.stringify(r.errors).slice(0, 200)}` : ""}`);
console.log(`\n${results.length} page loads, ${bad.length} with problems`);
process.exit(bad.length ? 1 : 0);
