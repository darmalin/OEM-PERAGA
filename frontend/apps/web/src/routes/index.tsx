import { createFileRoute, redirect } from "@tanstack/react-router";

import { requireMe } from "@/lib/guard";
import { visiblePanels } from "@/shell/nav";

export const Route = createFileRoute("/")({
  beforeLoad: async ({ context, location }) => {
    const me = await requireMe(context.queryClient, location.href);
    const first = visiblePanels(me)[0];
    throw redirect({ to: (first?.home ?? "/app") as "/" });
  },
});
