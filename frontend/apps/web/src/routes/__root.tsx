import type { QueryClient } from "@tanstack/react-query";
import { createRootRouteWithContext, Outlet } from "@tanstack/react-router";
import { Toaster } from "sonner";

import { useTheme } from "@/lib/theme";

function Root() {
  const theme = useTheme();
  return (
    <>
      <Outlet />
      {/* Toasts sit above content, so they are one of the few elements with a shadow. */}
      <Toaster
        position="bottom-right"
        visibleToasts={3}
        theme={theme}
        toastOptions={{
          classNames: {
            toast: "!rounded-[10px] !border !border-line !bg-bg !text-ink !shadow-overlay !font-sans !text-[13px]",
            description: "!text-label !tabular-nums",
            success: "[&_[data-icon]]:!text-[var(--green-fg)]",
            error: "[&_[data-icon]]:!text-[var(--red-fg)]",
          },
        }}
      />
    </>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: Root,
});
