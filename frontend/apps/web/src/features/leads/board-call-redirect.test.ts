import { createMemoryHistory, createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { expect, it } from "vitest";

import { Route as Board } from "@/routes/app/visitor-leads/board";
import { Route as LogCall } from "@/routes/app/visitor-leads/$leadId/log-call";

it("opens legacy board log-call links as a dialog on the board", async () => {
  const root = createRootRoute();
  const old = createRoute({ getParentRoute: () => root, path: "/app/visitor-leads/$leadId/log-call", validateSearch: LogCall.options.validateSearch, beforeLoad: (ctx) => LogCall.options.beforeLoad?.(ctx as never) });
  const board = createRoute({ getParentRoute: () => root, path: "/app/visitor-leads/board", validateSearch: Board.options.validateSearch });
  const router = createRouter({ routeTree: root.addChildren([old, board]), history: createMemoryHistory({ initialEntries: ["/app/visitor-leads/lead-1/log-call?to=RECONTACTED&from=board"] }) });
  await router.load();
  expect(router.state.location.pathname).toBe("/app/visitor-leads/board");
  expect(router.state.location.search).toMatchObject({ call_lead: "lead-1", call_to: "RECONTACTED" });
});
