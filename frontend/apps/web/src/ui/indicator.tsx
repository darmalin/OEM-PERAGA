import { cn } from "@/lib/cn";
import { label, type LabelGroup } from "@/lib/labels";
import { toneFor } from "@/lib/status";

/** Frappe indicator pill: dot + word. The one shape for every status (identity motif). */
export function Indicator({
  value,
  group,
  text,
  className,
}: {
  value: string | null | undefined;
  group?: LabelGroup;
  text?: string;
  className?: string;
}) {
  if (!value) return null;
  const tone = toneFor(value);
  return (
    <span
      className={cn(
        "inline-flex h-6 max-w-full items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium whitespace-nowrap",
        className,
      )}
      style={{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }}
    >
      <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden />
      <span className="truncate">{text ?? (group ? label(group, value) : value)}</span>
    </span>
  );
}
