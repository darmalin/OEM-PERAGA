import { formatNumber } from "@/lib/format";

import { Button } from "./button";
import { Select } from "./input";

export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-[13px] text-label">
      <span className="tabular">
        {formatNumber(from)} to {formatNumber(to)} of {formatNumber(total)}
      </span>
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2">
          <span>Rows</span>
          <Select
            className="h-7 w-[76px]"
            value={pageSize}
            onChange={(e) => onPageSize(Number(e.target.value))}
          >
            {[20, 100, 500].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Select>
        </label>
        <Button size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <span className="tabular">
          {page} / {pages}
        </span>
        <Button size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
