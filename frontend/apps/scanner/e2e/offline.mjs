// Offline flow against the running stack: activate, scan offline, go online, check the sync,
// send the same batch again, then revoke. Uses a locally installed Chromium.
//   EMS_URL=http://localhost:8080 EMS_SCANNER_URL=http://localhost:5174/scanner/ \
//   EMS_EMAIL=... EMS_PASSWORD=... CHROMIUM=/snap/bin/chromium node e2e/offline.mjs
import { chromium, request } from "playwright-core";

const API = process.env.EMS_URL ?? "http://localhost:8080";
const SCANNER = process.env.EMS_SCANNER_URL ?? "http://localhost:5174/scanner/";
const CODES = ["e2e-offline-001", "e2e-offline-002", "e2e-offline-001"];

function check(ok, what) {
  console.log(`${ok ? "ok  " : "FAIL"} ${what}`);
  if (!ok) process.exitCode = 1;
}

// Desk side: a supervisor creates a device on the first active gate it can see.
const desk = await request.newContext({ baseURL: API });
const login = await desk.post("/api/v1/auth/login", { data: { email: process.env.EMS_EMAIL, password: process.env.EMS_PASSWORD } });
if (!login.ok()) throw new Error(`login failed: ${login.status()}`);
const { csrf_token: csrf } = await login.json();
const headers = { "X-CSRF-Token": csrf };
const editions = await (await desk.get("/api/v1/editions?page_size=100")).json();
let gate;
for (const e of editions.items ?? editions) {
  if (e.status === "ARCHIVED") continue;
  gate = (await (await desk.get(`/api/v1/gates?edition_id=${e.id}`)).json()).find((g) => g.is_active);
  if (gate) break;
}
if (!gate) throw new Error("No active gate in a writable edition; create one in Gates first.");
const device = await (await desk.post("/api/v1/gate/devices", { headers, data: { gate_id: gate.id, name: `E2E offline ${Date.now()}` } })).json();

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/snap/bin/chromium", headless: true });
const ctx = await browser.newContext({ viewport: { width: 375, height: 812 }, reducedMotion: "reduce" });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

try {
  await page.goto(SCANNER);
  await page.getByLabel("Activation code").fill(device.activation_code);
  await page.getByRole("button", { name: "Activate Device" }).click();
  await page.getByRole("status").filter({ hasText: "Online" }).waitFor();
  check(await page.getByText(gate.name).isVisible(), "header shows the gate");
  // Offline checks need the credential list; a load-test edition takes a while to download.
  await page.getByText("No offline list yet").waitFor({ state: "detached", timeout: 120000 });

  await ctx.setOffline(true);
  await page.getByRole("button", { name: "Enter code manually" }).click();
  for (const code of CODES) {
    await page.getByLabel("QR code").fill(code);
    await page.getByRole("button", { name: "Check Code" }).click();
    await page.getByText("Provisional, will confirm when online.").waitFor();
    await page.getByRole("button", { name: "Dismiss result" }).click();
  }
  check(await page.getByText(`Offline (${CODES.length} pending)`).isVisible(), "offline with pending count");

  await ctx.setOffline(false);
  await page.getByRole("status").filter({ hasText: /^Online$/ }).waitFor({ timeout: 20000 });
  check(true, "pending count cleared after sync");

  // The same batch again, as after a lost response: the server must not count it twice.
  const replay = await page.evaluate(async () => {
    const open = indexedDB.open("ems-scanner");
    const db = await new Promise((r) => (open.onsuccess = () => r(open.result)));
    const all = (s) => new Promise((r) => { const q = db.transaction(s).objectStore(s).getAll(); q.onsuccess = () => r(q.result); });
    const [dev] = await all("device");
    const items = (await all("scan_queue")).map((s) => ({ scan_event_id: s.scan_event_id, token_hash: s.token_hash, scanned_at: s.scanned_at, provisional_result: s.provisional_result }));
    const res = await fetch("/api/v1/gate/device/scans/sync", { method: "POST", headers: { "content-type": "application/json", "X-Device-Token": dev.token }, body: JSON.stringify({ items }) });
    return { status: res.status, sent: items.length };
  });
  check(replay.status === 200 && replay.sent === CODES.length, "replayed batch accepted");
  const scans = await (await desk.get(`/api/v1/gate/scans?edition_id=${gate.edition_id}&device_id=${device.id}`)).json();
  check(scans.total === CODES.length, `server has ${CODES.length} scans, no duplicates (got ${scans.total})`);
  check(scans.items.every((s) => s.mode === "OFFLINE"), "scans recorded as offline");

  await desk.post(`/api/v1/gate/devices/${device.id}/revoke`, { headers, data: { reason: "E2E offline test" } });
  await page.reload();
  await page.getByText("This device cannot scan").waitFor();
  check(true, "revoked device shows the revoked screen");
  check(errors.length === 0, `no page errors ${errors.length ? JSON.stringify(errors) : ""}`);
} finally {
  await browser.close();
  await desk.dispose();
}
