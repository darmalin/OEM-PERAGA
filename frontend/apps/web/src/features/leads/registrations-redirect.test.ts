import { createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { Route as LegacyRegistrations } from "@/routes/app/registrations/index";
import { Route as RegistrationList } from "@/routes/app/visitor-leads/registrations";
import { Route as Leads } from "@/routes/app/visitor-leads/index";

import { registrationSearch } from "./registrations-search";

describe("Registrations within lead details", () => {
  it.each([
    { path: "/app/registrations", route: LegacyRegistrations },
    { path: "/app/visitor-leads/registrations", route: RegistrationList },
  ])("redirects $path to the plain leads list", async ({ path, route }) => {
    const root = createRootRoute();
    const old = createRoute({ getParentRoute: () => root, path, validateSearch: registrationSearch, beforeLoad: (ctx) => route.options.beforeLoad?.(ctx as never) });
    const leads = createRoute({ getParentRoute: () => root, path: "/app/visitor-leads", validateSearch: Leads.options.validateSearch });
    const router = createRouter({ routeTree: root.addChildren([old, leads]), history: createMemoryHistory({ initialEntries: [`${path}?page=2&page_size=100`] }) });
    await router.load();
    expect(router.state.location.pathname).toBe("/app/visitor-leads");
    expect(router.state.location.search).toMatchObject({ page: 2, page_size: 100 });
  });
});
