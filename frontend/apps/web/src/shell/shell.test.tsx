import { cleanup, render, screen, within } from "@testing-library/react";
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from "@tanstack/react-router";
import { afterEach, describe, expect, it } from "vitest";

import { PANELS } from "./nav";
import { Sidebar } from "./shell";

afterEach(cleanup);

describe("Sidebar active navigation", () => {
  it.each([
    ["/app", "Overview"],
    ["/app/visitor-leads", "Visitor Leads"],
    ["/app/visitor-leads/example", "Visitor Leads"],
    ["/app/visitor-leads/registrations", "Visitor Leads"],
    ["/app/registrations/example", "Visitor Leads"],
    ["/app/visitor-leads?search=test", "Visitor Leads"],
    ["/system", "Health"],
    ["/system/users", "Users"],
  ])("marks only the current menu at %s", async (path, label) => {
    const panel = PANELS.find((p) => path.startsWith(`/${p.id}`))!;
    const root = createRootRoute({ component: () => <Sidebar panel={panel} panels={PANELS} /> });
    const route = createRoute({ getParentRoute: () => root, path: "$" });
    const router = createRouter({
      routeTree: root.addChildren([route]),
      history: createMemoryHistory({ initialEntries: [path] }),
    });
    await router.load();
    render(<RouterProvider router={router} />);
    const nav = await screen.findByRole("navigation");
    const menuLinks = within(nav).getAllByRole("list").flatMap((list) => within(list).getAllByRole("link"));
    expect(menuLinks.filter((link) => link.getAttribute("aria-current") === "page").map((link) => link.textContent)).toEqual([label]);
  });
});
