import { Link, useRouter } from "@tanstack/react-router";

import { Button } from "./button";
import { ErrorState } from "./states";

/** Unexpected render or loader errors land here instead of a blank page (R-27). */
export function RouteError({ error }: { error: unknown }) {
  const router = useRouter();
  return (
    <div className="mx-auto max-w-xl px-6 py-16">
      <ErrorState error={error} onRetry={() => void router.invalidate()} />
    </div>
  );
}

export function RouteNotFound() {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-20 text-center">
      <p className="text-[16px] font-semibold">This page does not exist.</p>
      <p className="text-[13px] text-muted">The link may be old, or the page was moved.</p>
      <Button asChild variant="primary"><Link to="/">Go to Overview</Link></Button>
    </div>
  );
}
