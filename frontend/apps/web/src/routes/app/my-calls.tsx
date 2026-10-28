import { createFileRoute, redirect } from "@tanstack/react-router";
import { z } from "zod";

// Keep bookmarked queue URLs working after moving call work into Visitor Leads.
export const Route = createFileRoute("/app/my-calls")({
  validateSearch: z.object({
    view: z.enum(["mine", "team"]).default("mine"),
    agent_id: z.string().optional(),
    page: z.number().int().min(1).default(1),
    page_size: z.number().int().default(20),
  }),
  beforeLoad: ({ search }) => {
    throw redirect({
      to: "/app/visitor-leads",
      search: { owner: search.view === "team" ? search.agent_id : "me", page: search.page, page_size: search.page_size },
      replace: true,
    });
  },
});
