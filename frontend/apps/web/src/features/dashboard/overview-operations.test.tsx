import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { OverviewOperations } from "./overview-operations";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@ems/api", async (original) => ({ ...await original<typeof import("@ems/api")>(), api: { GET: (...args: unknown[]) => mocks.get(...args) }, call: (value: unknown) => value }));
beforeEach(() => {
  mocks.get.mockReset().mockImplementation((path: string) => Promise.resolve(path.endsWith("/visitors") ? { unique_event_visitors: 12, valid_entries: 20, repeat_entries: 6, rejected: 3 } : { totals: { sent: 50, waiting: 7, failed: 2, queued: 60 } }));
});
afterEach(cleanup);

async function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const root = createRootRoute({ component: () => <OverviewOperations s={{ from: "2026-10-01", to: "2026-10-28", edition: "edition-1" }} /> });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

it("shows unique scanned people separately from repeated entries and scopes both reports to the same edition and period", async () => {
  await show();
  expect(within(await screen.findByLabelText("Visitors Scanned")).getByText("12")).toBeVisible();
  expect(within(screen.getByLabelText("Valid Scans")).getByText("20")).toBeVisible();
  expect(within(screen.getByLabelText("Repeat Scans")).getByText("6")).toBeVisible();
  expect(within(screen.getByLabelText("Rejected Scans")).getByText("3")).toBeVisible();
  expect(within(await screen.findByLabelText("Emails Sent")).getByText("50")).toBeVisible();
  expect(within(screen.getByLabelText("Emails Waiting")).getByText("7")).toBeVisible();
  expect(mocks.get).toHaveBeenCalledWith("/api/v1/reports/visitors", { params: { query: { edition_id: "edition-1", report: "ATTENDANCE", date_from: "2026-10-01", date_to: "2026-10-28" } } });
  expect(mocks.get).toHaveBeenCalledWith("/api/v1/reports/dashboard/email", expect.objectContaining({ params: { query: expect.objectContaining({ edition_id: "edition-1", date_from: "2026-10-01", date_to: "2026-10-28" }) } }));
  expect(screen.getByRole("link", { name: "Email Report" })).toHaveAttribute("href", expect.stringContaining("tab=email"));
});

it("shows an error rather than a false zero when scan counts cannot load", async () => {
  mocks.get.mockImplementation((path: string) => path.endsWith("/visitors") ? Promise.reject(new Error("Scan report unavailable")) : Promise.resolve({ totals: { sent: 50, waiting: 7, failed: 2, queued: 60 } }));
  await show();
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(screen.queryByLabelText("Visitors Scanned")).not.toBeInTheDocument();
  expect(within(await screen.findByLabelText("Emails Sent")).getByText("50")).toBeVisible();
});
