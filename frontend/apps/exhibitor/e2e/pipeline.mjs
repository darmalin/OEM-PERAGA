// Exhibitor lead to paid, through the desk and the exhibitor portal UIs (FRONTEND_RULES/testing.md).
// Desk: booth, lead, Opportunity, booth hold, Convert. Portal: invitation link, password, contract,
// signed PDF. Desk: payment with proof, Verify. Portal: Paid. Then a password reset link and
// disabling / enabling the portal account.
//   EMS_URL=http://localhost:5173 EMS_EMAIL=... EMS_PASSWORD=... CHROMIUM=/snap/bin/chromium node e2e/pipeline.mjs
// The invitation link points at EMS_PUBLIC_BASE_URL/exhibitor (nginx :8080 -> `make portal`);
// PORTAL_URL=http://localhost:5176/exhibitor opens it on the portal dev server instead.
import { mkdirSync } from "node:fs";
import { chromium } from "playwright-core";

const DESK = process.env.EMS_URL ?? "http://localhost:5173";
// PORTAL_URL (optional) opens portal links on a portal dev server instead of nginx.
const portalLink = (url) => {
  if (!process.env.PORTAL_URL) return url;
  const u = new URL(url);
  return `${process.env.PORTAL_URL.replace(/\/$/, "")}${u.pathname.replace(/^\/exhibitor/, "")}${u.search}`;
};
const OUT = process.env.OUT ?? "e2e-out";
mkdirSync(OUT, { recursive: true });
const run = Date.now().toString(36);
const company = `E2E Exhibitor ${run}`;
const boothCode = `E2E-${run}`.slice(0, 20);
const PDF = Buffer.from("%PDF-1.7\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n");
const PNG = Buffer.from("89504e470d0a1a0a0000000d4948445200000001000000010806000000", "hex");

function check(ok, what) {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) process.exitCode = 1;
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
// Two contexts: staff and exhibitor never share cookies.
const desk = await (await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" })).newPage();
const portal = await (await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "dark" })).newPage();
const errors = [];
for (const [name, page] of [["desk", desk], ["portal", portal]]) {
  page.on("pageerror", (e) => errors.push(`${name}: ${e}`));
}
const toast = (text) => desk.locator("[data-sonner-toast]", { hasText: text }).first().waitFor({ timeout: 10000 });
/** Native HTML5 drag with real mouse steps; Playwright's dragTo did not start one on the board. */
async function drag(page, source, target) {
  const a = await source.boundingBox();
  const b = await target.boundingBox();
  const [x0, y0, x1, y1] = [a.x + a.width / 2, a.y + a.height - 15, b.x + b.width / 2, b.y + 60];
  await page.mouse.move(x0, y0);
  await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(x0 + ((x1 - x0) * i) / 10, y0 + ((y1 - y0) * i) / 10, { steps: 2 });
  await page.mouse.up();
}
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });

try {
  await desk.goto(`${DESK}/login`);
  await desk.getByLabel("Email").fill(process.env.EMS_EMAIL);
  await desk.getByLabel("Password").fill(process.env.EMS_PASSWORD);
  await desk.getByRole("button", { name: "Sign In" }).click();
  await desk.waitForURL(/\/app/);

  // Booth in the edition picked on the page head.
  await desk.goto(`${DESK}/app/booths/new`);
  await desk.getByLabel("Code").fill(boothCode);
  await desk.getByLabel("Area (m²)").fill("9");
  await desk.getByLabel("Price", { exact: false }).first().fill("15000000");
  await desk.getByRole("button", { name: "Save Booth" }).click();
  await toast(`Booth ${boothCode} added`);
  check(true, "booth added");

  await desk.goto(`${DESK}/app/exhibitor-leads/new`);
  await desk.getByLabel("Company Name").fill(company);
  await desk.getByLabel("Contact Name").fill("E2E Contact");
  await desk.getByLabel("Email").fill(`exhibitor-${run}@example.test`);
  await desk.getByRole("button", { name: "Save Exhibitor Lead" }).click();
  await desk.getByRole("heading", { name: company }).waitFor();
  check(true, "exhibitor lead created");

  await desk.getByRole("link", { name: "Assign", exact: true }).click();
  await desk.getByLabel("Lead Owner").selectOption({ index: 1 });
  await desk.getByRole("button", { name: "Save Owner" }).click();
  await toast("Assigned to");
  await desk.getByRole("link", { name: "Reassign" }).waitFor();
  check(true, "lead owner assigned");

  // Board: drag the card from Lead to Opportunity, then read its menu.
  const leadUrl = desk.url();
  await desk.goto(`${DESK}/app/exhibitor-leads/board`);
  const card = desk.locator("article", { hasText: company });
  await card.waitFor();
  await drag(desk, card, desk.getByRole("listitem", { name: /^Opportunity,/ }));
  await toast("Moved to Opportunity");
  await desk.getByRole("listitem", { name: /^Opportunity,/ }).locator("article", { hasText: company }).waitFor();
  check(true, "dragged to Opportunity on the board");
  await desk.getByRole("button", { name: `Move ${company}` }).click();
  const menu = await desk.getByRole("menuitem").allTextContents();
  check(
    JSON.stringify(menu) === JSON.stringify(["Lead", "Lost", "Exhibitor (choose a booth first)"]),
    `card menu offers ${menu.join(", ")}`,
  );
  await desk.keyboard.press("Escape");
  // Lost needs a reason: dropping there opens the stage page instead of moving.
  await drag(desk, desk.locator("article", { hasText: company }), desk.getByRole("listitem", { name: /^Lost,/ }));
  await desk.getByRole("heading", { name: "Move to Lost" }).waitFor();
  check(true, "drop on Lost opens the reason page");
  await desk.goto(leadUrl);

  await desk.getByRole("link", { name: "Choose Booth" }).click();
  await desk.getByRole("combobox").fill(boothCode);
  await desk.getByRole("option", { name: new RegExp(`^${boothCode}`) }).click();
  await desk.getByRole("button", { name: "Hold Booth" }).click();
  await toast(`Booth ${boothCode} held`);
  check(true, "booth held");

  await desk.getByRole("link", { name: "Convert to Exhibitor" }).click();
  await desk.getByRole("button", { name: "Convert to Exhibitor" }).click();
  const linkBox = desk.getByLabel("Invitation Link");
  await linkBox.waitFor();
  const invitation = await linkBox.inputValue();
  check(/\/exhibitor\/accept-invite\?token=/.test(invitation), "converted, invitation link shown");
  await shot(desk, "desk-converted");

  // Exhibitor side.
  await portal.goto(portalLink(invitation));
  await portal.getByRole("heading", { name: "Set Your Password" }).waitFor();
  await portal.getByLabel("New Password").fill(`exhibitor-${run}-pass`);
  await portal.getByLabel("Confirm Password").fill(`exhibitor-${run}-pass`);
  await portal.getByRole("button", { name: "Set Password and Sign In" }).click();
  await portal.getByRole("heading", { name: "My Exhibitions" }).waitFor();
  check(!portal.url().includes("token="), "password set, token gone from the address bar");

  await portal.getByText("Open exhibition").first().click(); // a new account has one exhibition
  await portal.getByLabel("PIC Name").fill("E2E Signer");
  await portal.getByLabel("Company Address").fill("Jl. E2E No. 1, Jakarta");
  await portal.getByRole("button", { name: "Save Details" }).click();
  await portal.getByText("Contract details saved.").waitFor();
  await portal.getByLabel(/^Signed PDF/).setInputFiles({ name: "signed.pdf", mimeType: "application/pdf", buffer: PDF });
  await portal.getByRole("button", { name: "Upload Signed Contract" }).click();
  await portal.getByRole("button", { name: "Download Signed Contract" }).waitFor();
  check(true, "contract filled and signed in the portal");
  await shot(portal, "portal-signed");

  // Staff record and verify the payment.
  // Wrong PDF: staff reopen the contract, the exhibitor uploads the right one.
  await desk.getByRole("link", { name: "Open Exhibitor" }).click();
  await desk.getByRole("tab", { name: "Contract" }).click();
  await desk.getByRole("link", { name: "Reopen Contract" }).click();
  await desk.getByLabel(/^Reason/).fill("Exhibitor uploaded last year's contract");
  await desk.getByRole("button", { name: "Reopen Contract" }).click();
  await toast("Contract reopened");
  await portal.reload();
  await portal.getByLabel(/^Signed PDF/).setInputFiles({ name: "signed-right.pdf", mimeType: "application/pdf", buffer: PDF });
  await portal.getByRole("button", { name: "Upload Signed Contract" }).click();
  await portal.getByRole("button", { name: "Download Signed Contract" }).waitFor();
  check(true, "contract reopened by staff and signed again in the portal");

  await desk.reload();
  await desk.getByRole("tab", { name: "Payments" }).click();
  await desk.getByRole("link", { name: "Record Payment" }).first().click();
  await desk.getByLabel(/^Amount/).fill("15000000");
  await desk.getByRole("button", { name: "Record Payment" }).click();
  await toast("Payment recorded");
  await desk.getByLabel("Transfer Slip or Receipt").setInputFiles({ name: "slip.png", mimeType: "image/png", buffer: PNG });
  await desk.getByRole("button", { name: "Attach" }).click();
  await toast("Proof attached");
  await desk.getByRole("button", { name: "Verify Payment" }).click();
  await toast("Payment verified");
  check(true, "payment recorded with proof and verified");

  await desk.getByRole("link", { name: company }).click();
  await desk.getByRole("tab", { name: "Payments" }).click();
  await desk.getByText("Paid", { exact: true }).first().waitFor();
  check(true, "desk shows Paid");
  await shot(desk, "desk-paid");

  await portal.reload();
  await portal.getByRole("heading", { name: "Payments" }).waitFor();
  check(await portal.getByText("Paid", { exact: true }).first().isVisible(), "portal shows Paid");
  await shot(portal, "portal-paid");

  // Forgotten password: staff make a reset link; the old session ends when it is used.
  await desk.getByRole("link", { name: "Password Reset Link" }).click();
  await desk.getByRole("button", { name: "Create Link" }).click();
  const resetBox = desk.getByLabel("Password Reset Link");
  await resetBox.waitFor();
  const resetUrl = await resetBox.inputValue();
  const phone = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  phone.on("pageerror", (e) => errors.push(`phone: ${e}`));
  await phone.goto(portalLink(resetUrl));
  await phone.getByRole("heading", { name: "Reset Your Password" }).waitFor();
  await phone.getByLabel("New Password").fill(`exhibitor-${run}-new`);
  await phone.getByLabel("Confirm Password").fill(`exhibitor-${run}-new`);
  await phone.getByRole("button", { name: "Save Password and Sign In" }).click();
  await phone.getByRole("heading", { name: "My Exhibitions" }).waitFor();
  await portal.reload();
  await portal.getByRole("heading", { name: "Sign In" }).waitFor();
  check(true, "password reset by link, other session signed out");

  // Disable, then enable the account.
  await desk.getByRole("link", { name: "Done" }).click();
  await desk.getByRole("link", { name: "Disable Account" }).click();
  await desk.getByRole("button", { name: "Disable Account" }).click();
  await toast("Portal account disabled");
  await phone.reload();
  await phone.getByRole("heading", { name: "Sign In" }).waitFor();
  await phone.getByLabel("Email").fill(`exhibitor-${run}@example.test`);
  await phone.getByLabel("Password").fill(`exhibitor-${run}-new`);
  await phone.getByRole("button", { name: "Sign In" }).click();
  await phone.getByText("Invalid email or password.").waitFor();
  await desk.getByRole("link", { name: "Enable Account" }).click();
  await desk.getByRole("button", { name: "Enable Account" }).click();
  await toast("Portal account enabled");
  await phone.getByRole("button", { name: "Sign In" }).click();
  await phone.getByRole("heading", { name: "My Exhibitions" }).waitFor();
  check(true, "disabled account cannot sign in; enabled again it can");

  // With a verified payment the contract cannot be reopened.
  await desk.getByRole("tab", { name: "Contract" }).click();
  await desk.getByRole("link", { name: "Reopen Contract" }).click();
  await desk.getByText(/verified payments, so it cannot be reopened/).waitFor();
  check(await desk.getByRole("button", { name: "Reopen Contract" }).count() === 0, "reopen blocked while payments exist");
  await shot(desk, "desk-portal-account");

  check(errors.length === 0, `no page errors ${errors.join(" | ")}`);
} catch (e) {
  check(false, String(e).split("\n")[0]);
  await shot(desk, "fail-desk").catch(() => {});
  await shot(portal, "fail-portal").catch(() => {});
} finally {
  await browser.close();
}
