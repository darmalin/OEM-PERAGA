import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Route } from "@/routes/system/users/$userId/index";

const mocks = vi.hoisted(() => ({ patch: vi.fn(), currentUserId: "admin" }));
const target = { id: "target", email: "target@example.test", full_name: "Test User", is_active: true, version: 1, role_assignments: [], team_ids: [], created_at: "2026-10-28T00:00:00Z", last_login_at: null };
vi.mock("@ems/api", () => ({
  api: { GET: (path: string) => Promise.resolve(path.includes("users/") ? target : []), PATCH: (...args: unknown[]) => mocks.patch(...args) },
  call: (value: unknown) => value,
}));
vi.mock("@/lib/auth", () => ({ useMe: () => ({ user: { id: mocks.currentUserId }, editions: [] }) }));
vi.mock("@/lib/notify", () => ({ notifySuccess: vi.fn(), notifyError: vi.fn() }));

beforeEach(() => {
  mocks.currentUserId = "admin";
  mocks.patch.mockReset().mockResolvedValue({ ...target, version: 2 });
  vi.spyOn(Route, "useParams").mockReturnValue({ userId: "target" });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const root = createRootRoute({ component: Route.options.component });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByRole("heading", { name: "Test User" });
  return userEvent.setup();
}

describe("User account controls", () => {
  it("requires matching passwords, sends only the new password and version, then clears both fields", async () => {
    const user = await show();
    await user.type(screen.getByLabelText(/^New Password/), "New-passphrase-2026");
    await user.type(screen.getByLabelText(/^Confirm New Password/), "different-password");
    await user.click(screen.getByLabelText(/^New Password/).closest("form")!.querySelector<HTMLButtonElement>('button[type="submit"]')!);
    expect(await screen.findByText("Passwords do not match.")).toBeVisible();
    expect(mocks.patch).not.toHaveBeenCalled();
    await user.clear(screen.getByLabelText(/^Confirm New Password/));
    await user.type(screen.getByLabelText(/^Confirm New Password/), "New-passphrase-2026");
    await user.click(screen.getByLabelText(/^New Password/).closest("form")!.querySelector<HTMLButtonElement>('button[type="submit"]')!);
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith("/api/v1/users/{user_id}", { params: { path: { user_id: "target" } }, body: { version: 1, password: "New-passphrase-2026" } }));
    await waitFor(() => expect(screen.getByLabelText(/^New Password/)).toHaveValue(""));
    expect(screen.getByLabelText(/^Confirm New Password/)).toHaveValue("");
  });

  it("requires confirmation to disable and offers re-enabling afterwards", async () => {
    mocks.patch.mockResolvedValue({ ...target, version: 2, is_active: false });
    const user = await show();
    await user.click(screen.getByRole("button", { name: "Disable User" }));
    expect(mocks.patch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm Disable" }));
    expect(await screen.findByRole("button", { name: "Enable User" })).toBeEnabled();
    expect(mocks.patch).toHaveBeenLastCalledWith("/api/v1/users/{user_id}", { params: { path: { user_id: "target" } }, body: { version: 1, is_active: false } });
    await user.click(screen.getByRole("button", { name: "Enable User" }));
    await waitFor(() => expect(mocks.patch).toHaveBeenLastCalledWith("/api/v1/users/{user_id}", { params: { path: { user_id: "target" } }, body: { version: 2, is_active: true } }));
  });

  it("prevents disabling the signed-in account", async () => {
    mocks.currentUserId = "target";
    await show();
    expect(screen.getByRole("button", { name: "Disable User" })).toBeDisabled();
  });
});
