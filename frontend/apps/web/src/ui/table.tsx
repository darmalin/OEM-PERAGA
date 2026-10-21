import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

import { Checkbox } from "./checkbox";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  className?: string;
  /** Hidden below this breakpoint; the first column and the link stay. */
  hideBelow?: "md" | "lg" | "xl" | "2xl";
}

interface ListTableProps<T> {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  rowLink?: (row: T) => { to: string; params?: Record<string, string> };
  selected?: Set<string>;
  onToggle?: (id: string) => void;
  onToggleAll?: (checked: boolean) => void;
  caption: string;
}

const HIDE = { md: "max-md:hidden", lg: "max-lg:hidden", xl: "max-xl:hidden", "2xl": "max-2xl:hidden" } as const;

/** Frappe list: line separators, 40px rows, whole first cell links to the record. */
export function ListTable<T>({ rows, columns, rowKey, rowLink, selected, onToggle, onToggleAll, caption }: ListTableProps<T>) {
  const allChecked = selected ? rows.length > 0 && rows.every((r) => selected.has(rowKey(r))) : false;
  const [first, ...rest] = columns;
  // Phones get stacked rows: the first column as the title, the columns that matter below it.
  const mobileMeta = rest.filter((c) => !c.hideBelow);
  return (
    <>
    <ul className="divide-y divide-line md:hidden" aria-label={caption}>
      {rows.map((row) => {
        const id = rowKey(row);
        const link = rowLink?.(row);
        return (
          <li key={id} className="flex items-start gap-3 px-4 py-3">
            {selected ? (
              <Checkbox className="mt-0.5" checked={selected.has(id)} onCheckedChange={() => onToggle?.(id)} aria-label="Select row" />
            ) : null}
            <div className="min-w-0 flex-1">
              {first ? (
                link ? (
                  <Link to={link.to as "/"} params={link.params as never} className="block rounded-[4px] text-[14px] font-medium text-ink">
                    {first.cell(row)}
                  </Link>
                ) : (
                  <div className="text-[14px] font-medium">{first.cell(row)}</div>
                )
              ) : null}
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px] text-muted">
                {mobileMeta.map((c) => (
                  <span key={c.key} className="max-w-full truncate">{c.cell(row)}</span>
                ))}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
    <div className="overflow-x-auto max-md:hidden">
      <table className="w-full border-collapse text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-left text-[12px] text-label">
            {selected ? (
              <th scope="col" className="w-10 px-4 py-2.5">
                <Checkbox
                  checked={allChecked}
                  onCheckedChange={(c) => onToggleAll?.(c === true)}
                  aria-label="Select all rows on this page"
                />
              </th>
            ) : null}
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cn("px-4 py-2.5 font-normal whitespace-nowrap", c.hideBelow && HIDE[c.hideBelow], c.className)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const id = rowKey(row);
            const link = rowLink?.(row);
            return (
              // Generic component: rowLink returns a real route path.
              <tr key={id} className="border-b border-line last:border-b-0 hover:bg-subtle has-[:focus-visible]:bg-subtle">
                {selected ? (
                  <td className="px-4 py-2">
                    <Checkbox
                      checked={selected.has(id)}
                      onCheckedChange={() => onToggle?.(id)}
                      aria-label="Select row"
                    />
                  </td>
                ) : null}
                {columns.map((c, i) => (
                  <td key={c.key} className={cn("h-10 max-w-[280px] px-4 py-2 align-middle", c.hideBelow && HIDE[c.hideBelow], c.className)}>
                    {i === 0 && link ? (
                      <Link to={link.to as "/"} params={link.params as never} className="block truncate rounded-[4px] font-medium text-ink hover:underline">
                        {c.cell(row)}
                      </Link>
                    ) : (
                      <div className="truncate">{c.cell(row)}</div>
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </>
  );
}
