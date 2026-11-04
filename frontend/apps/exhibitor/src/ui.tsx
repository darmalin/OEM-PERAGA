import { cn } from "@ems/ui/cn";
import { Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes, useId } from "react";

import { label, toneOf } from "./lib";

// Same look as the desk (DESIGN.md): filled inputs, ink primary, 8px radius.
const control =
  "w-full rounded-[8px] bg-input px-3 text-[14px] text-ink placeholder:text-label hover:bg-hover disabled:cursor-not-allowed disabled:text-muted aria-[invalid=true]:ring-1 aria-[invalid=true]:ring-[var(--required)]";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(control, "h-10", className)} {...props} />
));
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(control, "min-h-24 py-2 leading-5", className)} {...props} />
));
Textarea.displayName = "Textarea";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  loading?: boolean;
}

export function Button({ variant = "secondary", loading, disabled, className, children, ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-1.5 rounded-[8px] px-4 text-[14px] font-medium whitespace-nowrap disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4",
        variant === "primary" && "bg-primary text-on-primary hover:opacity-90",
        variant === "secondary" && "bg-input text-ink hover:bg-hover",
        variant === "ghost" && "text-ink hover:bg-hover",
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="animate-spin" aria-hidden /> : null}
      {children}
    </button>
  );
}

/** Label above, required star, help or error linked by aria-describedby. */
export function Field({
  label: text,
  required,
  help,
  error,
  className,
  children,
}: {
  label: string;
  required?: boolean;
  help?: ReactNode;
  error?: string | undefined;
  className?: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => ReactNode;
}) {
  const id = useId();
  const describedBy = error ? `${id}-error` : help ? `${id}-help` : undefined;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[13px] text-label">
        {text}
        {required ? <span className="ml-0.5 text-required" aria-hidden> *</span> : null}
        {required ? <span className="sr-only"> (required)</span> : null}
      </label>
      {children({ id, "aria-invalid": Boolean(error), ...(describedBy ? { "aria-describedby": describedBy } : {}) })}
      {error ? (
        <p id={`${id}-error`} className="text-[12px] text-required">{error}</p>
      ) : help ? (
        <p id={`${id}-help`} className="text-[12px] text-label">{help}</p>
      ) : null}
    </div>
  );
}

/** Dot + word, the one shape for every status (DESIGN.md "Status indicators"). */
export function Status({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  const tone = toneOf(value);
  return (
    <span
      className="inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium whitespace-nowrap"
      style={{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {label(value)}
    </span>
  );
}

export function Panel({ title, aside, children, className }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-[12px] border border-line bg-bg", className)}>
      {title ? (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3 max-sm:px-4">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          {aside}
        </header>
      ) : null}
      <div className="px-5 py-5 max-sm:px-4">{children}</div>
    </section>
  );
}

export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,140px)_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-[14px] max-sm:grid-cols-1 max-sm:gap-y-0.5">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-label max-sm:mt-2">{k}</dt>
          <dd className="min-w-0 break-words">{v || <span className="text-label">Not set</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Notice({ tone = "red", children }: { tone?: "red" | "green" | "amber"; children: ReactNode }) {
  return (
    <p role={tone === "red" ? "alert" : "status"} className="rounded-[8px] px-3 py-2.5 text-[13px]" style={{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }}>
      {children}
    </p>
  );
}
