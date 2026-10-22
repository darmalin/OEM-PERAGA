import "./styles/app.css";

import { QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { queryClient } from "./lib/query";
import { RouteError, RouteNotFound } from "./ui/route-states";
import { watchSystemTheme } from "./lib/theme";
import { routeTree } from "./routeTree.gen";

const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
  defaultErrorComponent: RouteError,
  defaultNotFoundComponent: RouteNotFound,
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
  // Data handed to the next page without putting it in the URL.
  interface HistoryState {
    leadIds?: string[];
    /** Edition of the leads handed to the assign page (the list can span editions). */
    editionId?: string;
    activationCode?: string;
  }
}

watchSystemTheme();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
