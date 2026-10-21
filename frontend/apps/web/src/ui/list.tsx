import type { ReactNode } from "react";

import { Pagination } from "./pagination";
import { ErrorState, TableSkeleton } from "./states";

interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** States for every list: loading skeleton, error with retry, empty with a next step (R-27). */
export function ListBody<T>({
  query,
  empty,
  children,
  onPage,
  onPageSize,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data?: PageResult<T>; refetch: () => unknown };
  empty: ReactNode;
  children: (items: T[]) => ReactNode;
  onPage?: (p: number) => void;
  onPageSize?: (n: number) => void;
}) {
  if (query.isPending) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (query.data.items.length === 0) return <>{empty}</>;
  return (
    <>
      {children(query.data.items)}
      {onPage && onPageSize ? (
        <Pagination page={query.data.page} pageSize={query.data.page_size} total={query.data.total} onPage={onPage} onPageSize={onPageSize} />
      ) : null}
    </>
  );
}

/** Same states for plain arrays (endpoints that are not paginated). */
export function ArrayBody<T>({
  query,
  empty,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data?: T[]; refetch: () => unknown };
  empty: ReactNode;
  children: (items: T[]) => ReactNode;
}) {
  if (query.isPending) return <TableSkeleton />;
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (query.data.length === 0) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
