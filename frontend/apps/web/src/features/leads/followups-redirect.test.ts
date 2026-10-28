import { createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { Route as OldFollowups } from "@/routes/app/followups/index";
import { Route as Leads } from "@/routes/app/visitor-leads/index";

describe("Retired Follow-ups list", () => {
  it("redirects old links to Visitor Leads without carrying obsolete filters", async () => {
    const root = createRootRoute();
    const old = createRoute({ getParentRoute: () => root, path: "/app/followups", beforeLoad: (ctx) => OldFollowups.options.beforeLoad?.(ctx as never) });
    const leads = createRoute({ getParentRoute: () => root, path: "/app/visitor-leads", validateSearch: Leads.options.validateSearch });
    const router = createRouter({ routeTree: root.addChildren([old, leads]), history: createMemoryHistory({ initialEntries: ["/app/followups?bucket=overdue&status=OPEN"] }) });
    await router.load();
    expect(router.state.location.pathname).toBe("/app/visitor-leads");
    expect(router.state.location.search).toEqual({ page: 1, page_size: 20 });
  });
});
