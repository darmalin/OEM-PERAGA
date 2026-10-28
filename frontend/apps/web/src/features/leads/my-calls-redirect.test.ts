import { createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { Route as OldCalls } from "@/routes/app/my-calls";
import { Route as Leads } from "@/routes/app/visitor-leads/index";

describe("Retired My Calls page", () => {
  it.each([
    { url: "/app/my-calls", owner: "me", page: 1 },
    { url: "/app/my-calls?view=team&agent_id=agent-123&page=2&page_size=100", owner: "agent-123", page: 2 },
  ])("redirects $url to the corresponding leads", async ({ url, owner, page }) => {
    const root = createRootRoute();
    const old = createRoute({ getParentRoute: () => root, path: "/app/my-calls", validateSearch: OldCalls.options.validateSearch, beforeLoad: (ctx) => OldCalls.options.beforeLoad?.(ctx as never) });
    const leads = createRoute({ getParentRoute: () => root, path: "/app/visitor-leads", validateSearch: Leads.options.validateSearch });
    const router = createRouter({ routeTree: root.addChildren([old, leads]), history: createMemoryHistory({ initialEntries: [url] }) });
    await router.load();
    expect(router.state.location.pathname).toBe("/app/visitor-leads");
    expect(router.state.location.search).toMatchObject({ owner, page });
  });
});
