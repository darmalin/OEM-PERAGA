import { createFileRoute, redirect } from "@tanstack/react-router";

// Follow-up work starts from the lead; retain old bookmarks without a separate list.
export const Route = createFileRoute("/app/followups/")({
  beforeLoad: () => {
    throw redirect({ to: "/app/visitor-leads", search: { page: 1, page_size: 20 }, replace: true });
  },
});
