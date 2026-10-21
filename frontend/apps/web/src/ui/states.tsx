import { ApiError } from "@ems/api";
import type { ReactNode } from "react";

import { Button } from "./button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? "h-4 w-full"}`} aria-hidden />;
}

export function TableSkeleton({ rows = 8, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="divide-y divide-line">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex h-10 items-center gap-4 px-4">
          <Skeleton className="h-3.5 w-1/4" />
          <Skeleton className="h-3.5 w-1/5" />
          <Skeleton className="h-3.5 w-1/6" />
          <Skeleton className="ml-auto h-3.5 w-16" />
        </div>
      ))}
    </div>
  );
}

export function FormSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="grid grid-cols-1 gap-x-6 gap-y-5 p-5 md:grid-cols-3">
      {Array.from({ length: 9 }, (_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-full" />
        </div>
      ))}
    </div>
  );
}

/** One sentence of cause and one action (DESIGN.md "States"). */
export function EmptyState({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <p className="max-w-md text-[14px] text-muted">{title}</p>
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
    return <NoAccess message={error.status === 404 ? error.message : undefined} />;
  }
  const message = error instanceof ApiError ? error.message : "The server could not be reached.";
  const rid = error instanceof ApiError ? error.requestId : null;
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <p className="text-[14px] font-medium text-ink">Could not load this page.</p>
      <p className="max-w-md text-[13px] text-muted">{message}</p>
      {onRetry ? <Button onClick={onRetry}>Retry</Button> : null}
      {rid ? <p className="text-[12px] text-label tabular">Request ID {rid}</p> : null}
    </div>
  );
}

export function NoAccess({ message }: { message?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="text-[14px] font-medium">{message ?? "You don't have access to this."}</p>
      <p className="text-[13px] text-muted">Ask an administrator if you need it.</p>
    </div>
  );
}

export function NoEdition() {
  return (
    <EmptyState title="No edition is available to you yet. An administrator has to create an edition or give you access to one." />
  );
}
