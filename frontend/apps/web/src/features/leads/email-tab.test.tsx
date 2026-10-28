import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LeadEmailTab } from "./email-tab";

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock("@ems/api", () => ({ api: { GET: (...args: unknown[]) => mocks.get(...args) }, call: (value: unknown) => value }));
const history = {
  total: 42, sent_count: 40, pending_count: 0, failed_count: 1, cancelled_count: 1, page: 1, page_size: 20,
  items: [
    { id: "email-1", kind: "QR_CONFIRMATION", recipient: "visitor@example.test", subject: "Your event confirmation", status: "SENT", attempts: 2, from_address: "events@example.test", queued_at: "2026-10-28T00:00:00Z", sent_at: "2026-10-28T00:01:00Z", error_summary: null },
    { id: "email-2", kind: "QR_CONFIRMATION", recipient: "old@example.test", subject: null, status: "FAILED", attempts: 3, from_address: null, queued_at: "2026-10-27T00:00:00Z", sent_at: null, error_summary: "SMTP 550" },
  ],
};
beforeEach(() => { mocks.get.mockReset().mockResolvedValue(history); });
afterEach(cleanup);

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><LeadEmailTab leadId="lead-123" timezone="Asia/Jakarta" /></QueryClientProvider>);
  return userEvent.setup();
}

describe("Lead email history", () => {
  it("shows whole-history counts, subjects, recipients and failure information", async () => {
    show();
    expect(await screen.findByText("Your event confirmation")).toBeVisible();
    const sent = screen.getAllByText("Sent").find((element) => element.parentElement?.textContent === "Sent40")!;
    expect(within(sent.parentElement!).getByText("40")).toBeVisible();
    expect(screen.getByText("Total Emails").parentElement).toHaveTextContent("42");
    expect(screen.getByText("visitor@example.test")).toBeVisible();
    expect(screen.getByText("old@example.test")).toBeVisible();
    expect(screen.getByText("SMTP 550")).toBeVisible();
    expect(mocks.get).toHaveBeenCalledWith("/api/v1/visitor-leads/{lead_id}/emails", { params: { path: { lead_id: "lead-123" }, query: { page: 1, page_size: 20 } } });
  });

  it("paginates the lead's history and can refresh it", async () => {
    const user = show();
    await screen.findByText("Your event confirmation");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(mocks.get).toHaveBeenLastCalledWith("/api/v1/visitor-leads/{lead_id}/emails", { params: { path: { lead_id: "lead-123" }, query: { page: 2, page_size: 20 } } }));
    const before = mocks.get.mock.calls.length;
    await user.click(await screen.findByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(mocks.get.mock.calls.length).toBeGreaterThan(before));
  });

  it("shows an empty state and zero counts for a lead without email", async () => {
    mocks.get.mockResolvedValue({ ...history, items: [], total: 0, sent_count: 0, failed_count: 0, cancelled_count: 0 });
    show();
    expect(await screen.findByText("No emails have been recorded for this lead yet.")).toBeVisible();
    expect(screen.getByText("Total Emails").parentElement).toHaveTextContent("0");
  });
});
