import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Route as TeamRoute } from "@/routes/system/teams/$teamId";

const mocks = vi.hoisted(() => ({ patch: vi.fn(), post: vi.fn(), remove: vi.fn(), team: { id: "team-1", name: "Sales", is_active: true, version: 1, member_ids: ["inactive"] as string[] } }));
vi.mock("@ems/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@ems/api")>(),
  api: {
    GET: (path: string) => Promise.resolve(path.includes("member-options") ? { items: [{ id: "a", full_name: "Agent One", email: "one@example.test", is_active: true }, { id: "b", full_name: "Agent Two", email: "two@example.test", is_active: true }], total: 2 } : path.includes("users") ? { items: [{ id: "a", full_name: "Agent One", email: "one@example.test", is_active: true }, { id: "b", full_name: "Agent Two", email: "two@example.test", is_active: true }, { id: "inactive", full_name: "Former Agent", email: "former@example.test", is_active: false }, { id: "manager", full_name: "Team Manager", email: "manager@example.test", is_active: true }], total: 4 } : { ...mocks.team }),
    PATCH: (...args: unknown[]) => mocks.patch(...args), POST: (...args: unknown[]) => mocks.post(...args), DELETE: (...args: unknown[]) => mocks.remove(...args),
  }, call: (value: unknown) => value,
}));
vi.mock("@/lib/notify", () => ({ notifySuccess: vi.fn(), notifyError: vi.fn() }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  mocks.team = { id: "team-1", name: "Sales", is_active: true, version: 1, member_ids: ["inactive"] };
  mocks.patch.mockReset().mockImplementation((_path, options) => { mocks.team = { ...mocks.team, ...options.body, version: mocks.team.version + 1 }; return Promise.resolve({ ...mocks.team }); });
  mocks.post.mockReset().mockImplementation((_path, options) => { mocks.team = { ...mocks.team, member_ids: [...mocks.team.member_ids, ...options.body.user_ids], version: mocks.team.version + 1 }; return Promise.resolve({ ...mocks.team }); });
  mocks.remove.mockReset().mockResolvedValue(undefined);
  vi.spyOn(TeamRoute, "useParams").mockReturnValue({ teamId: "team-1" });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
async function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const root = createRootRoute();
  const detail = createRoute({ getParentRoute: () => root, path: "/system/teams/$teamId", component: TeamRoute.options.component });
  const list = createRoute({ getParentRoute: () => root, path: "/system/teams", component: () => <p>Team list</p> });
  const router = createRouter({ routeTree: root.addChildren([detail, list]), history: createMemoryHistory({ initialEntries: ["/system/teams/team-1"] }) });
  await router.load(); render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  await screen.findByRole("heading", { name: "Sales" }); return userEvent.setup();
}

describe("Flexible team management", () => {
  it("edits the name and adds several users without hiding disabled existing members", async () => {
    const user = await show();
    expect(await screen.findByText("Former Agent")).toBeVisible();
    expect(screen.getByText("Disabled user")).toBeVisible();
    expect(screen.queryByRole("checkbox", { name: /Team Manager/ })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText(/^Name/)); await user.type(screen.getByLabelText(/^Name/), "New Sales");
    await user.click(screen.getByRole("button", { name: "Save Team" }));
    await screen.findByRole("heading", { name: "New Sales" });
    await user.click(screen.getByRole("checkbox", { name: /Agent One/ })); await user.click(screen.getByRole("checkbox", { name: /Agent Two/ }));
    await user.click(screen.getByRole("button", { name: "Add Selected Members (2)" }));
    await waitFor(() => expect(mocks.post).toHaveBeenCalledWith("/api/v1/teams/{team_id}/members/batch", { params: { path: { team_id: "team-1" } }, body: { user_ids: ["a", "b"] } }));
    await waitFor(() => expect(screen.getByText("3 members")).toBeVisible());
  });
  it("confirms disable, retains members and allows enabling again", async () => {
    const user = await show();
    await user.click(screen.getByRole("button", { name: "Disable Team" })); expect(mocks.patch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm Disable" }));
    await user.click(await screen.findByRole("button", { name: "Enable Team" }));
    await screen.findByRole("button", { name: "Disable Team" });
    expect(mocks.team.is_active).toBe(true); expect(mocks.team.member_ids).toEqual(["inactive"]);
  });
  it("requires confirmation before deleting a team", async () => {
    const user = await show();
    await user.click(screen.getByRole("button", { name: "Delete Team" })); expect(mocks.remove).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm Delete" }));
    expect(await screen.findByText("Team list")).toBeVisible();
    expect(mocks.remove).toHaveBeenCalledWith("/api/v1/teams/{team_id}", { params: { path: { team_id: "team-1" }, query: { version: 1 } } });
  });
});
