import { createFileRoute, Outlet } from "@tanstack/react-router";

import { EditionProvider } from "@/lib/edition";
import { requireMe } from "@/lib/guard";
import { Shell } from "@/shell/shell";

export const Route = createFileRoute("/system")({
  beforeLoad: ({ context, location }) => requireMe(context.queryClient, location.href),
  component: () => (
    <EditionProvider>
      <Shell panelId="system">
        <Outlet />
      </Shell>
    </EditionProvider>
  ),
});
