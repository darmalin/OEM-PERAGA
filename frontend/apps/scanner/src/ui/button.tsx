import { cn } from "@ems/ui/cn";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary";

/** Scanner controls are at least 56px tall (DESIGN.md "Scanner"). */
export function Button({
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex min-h-14 items-center justify-center gap-2 rounded-control px-5 text-lg font-medium",
        "disabled:opacity-50",
        variant === "primary" ? "bg-primary text-on-primary" : "bg-input text-ink active:bg-hover",
        className,
      )}
      {...props}
    />
  );
}
