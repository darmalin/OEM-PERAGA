import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";

/** A real number with its label. Never a placeholder value (R-17). */
export function Metric({
  label,
  value,
  hint,
  tone = "default",
  className,
}: {
  label: string;
  value: number | string | null | undefined;
  hint?: ReactNode;
  tone?: "default" | "band";
  className?: string;
}) {
  const shown = typeof value === "number" ? formatNumber(value) : (value ?? "");
  return (
    <div className={cn("min-w-0", className)}>
      <p className={cn("text-[12px]", tone === "band" ? "text-on-band-muted" : "text-label")}>{label}</p>
      <p className="mt-0.5 text-[22px] leading-7 font-semibold tracking-[-0.01em] tabular">{shown}</p>
      {hint ? <p className={cn("mt-0.5 text-[12px]", tone === "band" ? "text-on-band-muted" : "text-label")}>{hint}</p> : null}
    </div>
  );
}

/** Horizontal bar list for breakdowns; the bar is the value, the number is exact. */
export function BarList({ rows, labelFor }: { rows: { key: string | null; count: number }[]; labelFor: (k: string | null) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <li key={r.key ?? "none"} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-[13px]">
          <span className="truncate">{labelFor(r.key)}</span>
          <span className="font-medium tabular">{formatNumber(r.count)}</span>
          <span className="col-span-2 h-1.5 rounded-full bg-input" aria-hidden>
            <span className="block h-full rounded-full bg-primary" style={{ width: `${(r.count / max) * 100}%` }} />
          </span>
        </li>
      ))}
    </ul>
  );
}
