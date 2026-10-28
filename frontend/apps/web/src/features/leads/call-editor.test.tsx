import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CallEditor } from "./call-editor";

const mocks = vi.hoisted(() => ({ post: vi.fn(), done: vi.fn(), cancel: vi.fn() }));
vi.mock("@ems/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@ems/api")>(),
  api: {
    GET: (path: string) => Promise.resolve(path.includes("call-results") ? ["ANSWER", "NO_ANSWER"] : { id: "lead-1", first_name: "Test Visitor", edition_id: "edition-1", registration_code: "TEST001", phone: "123", telemarketing_status: "ANSWER", attend: null, buyer_type: null, b2b_matching: false }),
    POST: (...args: unknown[]) => mocks.post(...args),
  },
  call: (value: unknown) => value,
}));
vi.mock("@/lib/edition", () => ({ useEditionById: () => ({ timezone: "Asia/Jakarta" }) }));
vi.mock("@/lib/notify", () => ({ notifySuccess: vi.fn(), notifyError: vi.fn() }));

beforeEach(() => { vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} }); mocks.post.mockReset().mockResolvedValue({ telemarketing_status: "RECONTACTED", call: { attempt_number: 2 }, followup_id: null }); mocks.done.mockReset(); mocks.cancel.mockReset(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CallEditor leadId="lead-1" to="RECONTACTED" onComplete={mocks.done} onCancel={mocks.cancel} /></QueryClientProvider>);
  return userEvent.setup();
}

describe("Board call editor", () => {
  it("preselects the dropped outcome, validates Attend, and saves the complete call before closing", async () => {
    const user = show();
    const answered = await screen.findByRole("radio", { name: "Answer to Recontacted" });
    await waitFor(() => expect(answered).toBeChecked());
    await user.click(screen.getByRole("button", { name: "Save and Move" }));
    expect(await screen.findByText("Attend is required for an answered call.")).toBeVisible();
    expect(mocks.post).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Next Follow-up")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText(/^Attend/), "ATTEND");
    await user.type(screen.getByLabelText("Notes"), "Visitor confirmed attendance");
    await user.click(screen.getByRole("button", { name: "Save and Move" }));
    await waitFor(() => expect(mocks.done).toHaveBeenCalledOnce());
    expect(mocks.post).toHaveBeenCalledWith("/api/v1/visitor-leads/{lead_id}/calls", expect.objectContaining({
      params: { path: { lead_id: "lead-1" } }, body: expect.objectContaining({ call_result: "ANSWER", notes: "Visitor confirmed attendance", verification: { lead_quality: "VALID", attend: "ATTEND", buyer_type: null, b2b_matching: false } }),
    }));
    expect(mocks.post.mock.calls[0]?.[1].body).not.toHaveProperty("next_followup_at");
  });

  it("moves an unanswered call after Answer to Retry No Answer", async () => {
    mocks.post.mockResolvedValue({ telemarketing_status: "RETRY_NO_ANSWER", call: { attempt_number: 2 }, followup_id: null });
    const user = show();
    const unanswered = await screen.findByRole("radio", { name: "Answer to Retry No Answer" });
    await user.click(unanswered);
    await user.click(screen.getByRole("radio", { name: "Undecided" }));
    await user.click(screen.getByRole("button", { name: "Save and Move" }));
    await waitFor(() => expect(mocks.done).toHaveBeenCalledOnce());
    expect(mocks.post).toHaveBeenCalledWith("/api/v1/visitor-leads/{lead_id}/calls", expect.objectContaining({ body: expect.objectContaining({ call_result: "NO_ANSWER", verification: { lead_quality: "UNDECIDED" } }) }));
  });

  it("cancels without recording a call", async () => {
    const user = show();
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(mocks.cancel).toHaveBeenCalledOnce();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("keeps the form and notes open when saving fails", async () => {
    mocks.post.mockRejectedValue(new Error("Connection failed"));
    const user = show();
    await user.selectOptions(await screen.findByLabelText(/^Attend/), "ATTEND");
    await user.type(screen.getByLabelText("Notes"), "Keep these notes");
    await user.click(screen.getByRole("button", { name: "Save and Move" }));
    await waitFor(() => expect(mocks.post).toHaveBeenCalledOnce());
    expect(mocks.done).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Notes")).toHaveValue("Keep these notes");
  });
});
