import { createFileRoute, redirect } from "@tanstack/react-router";

import { registrationSearch } from "@/features/leads/registrations-search";

// Registrations are opened from each lead's Registration tab.
export const Route = createFileRoute("/app/visitor-leads/registrations")({
  validateSearch: registrationSearch,
  beforeLoad: ({ search }) => {
    throw redirect({ to: "/app/visitor-leads", search: { page: search.page, page_size: search.page_size }, replace: true });
  },
});
