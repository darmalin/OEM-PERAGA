import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { Route as EditRoute } from "@/routes/app/lead-sources/$sourceId";
import { Route as ListRoute } from "@/routes/app/lead-sources/index";
import { Route as NewRoute } from "@/routes/app/lead-sources/new";

const state = vi.hoisted(() => ({ global: false }));
vi.mock("@/lib/auth", async (original) => ({ ...await original<typeof import("@/lib/auth")>(), useMe: () => ({ permissions: ["exhibition.manage"], global_permissions: state.global ? ["exhibition.manage"] : [] }) }));
vi.mock("@ems/api", async (original) => ({ ...await original<typeof import("@ems/api")>(), api: { GET: () => Promise.resolve([]) }, call: (value: unknown) => value }));
beforeEach(() => { state.global = false; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function show(component: typeof ListRoute.options.component) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const root = createRootRoute({ component });
  const router = createRouter({ routeTree: root, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

it("does not offer global source management for an edition-only permission", async () => {
  await show(ListRoute.options.component);
  await screen.findByRole("heading", { name: "Sources" });
  expect(screen.queryByRole("link", { name: "Add Source" })).not.toBeInTheDocument();
});

it("offers Add Source when the account has a global management grant", async () => {
  state.global = true;
  await show(ListRoute.options.component);
  expect((await screen.findAllByRole("link", { name: "Add Source" })).length).toBeGreaterThan(0);
});

it("explains the global permission requirement on the direct create URL", async () => {
  await show(NewRoute.options.component);
  expect(await screen.findByText("Sources are shared across all exhibitions. A global administrator is required to manage them.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save Source" })).not.toBeInTheDocument();
});

it("also blocks the edit form for an edition-only management grant", async () => {
  vi.spyOn(EditRoute, "useParams").mockReturnValue({ sourceId: "source-1" });
  await show(EditRoute.options.component);
  expect(await screen.findByText("Sources are shared across all exhibitions. A global administrator is required to manage them.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save Source" })).not.toBeInTheDocument();
});
