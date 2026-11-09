import { cn } from "@ems/ui/cn";
import { Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes, useId } from "react";

import { label, toneOf } from "./lib";

// Portal look (styles.css): white fields with a visible edge on the pale page, indigo actions,
// 10px controls and 16px cards so it reads as a friendly app, not the desk's dense forms.
const control =
  "w-full rounded-[10px] border border-line-strong bg-bg px-3.5 text-[15px] text-ink placeholder:text-label hover:border-primary/40 disabled:cursor-not-allowed disabled:bg-page disabled:text-muted aria-[invalid=true]:border-[var(--required)]";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(control, "h-11", className)} {...props} />
));
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(control, "min-h-24 py-2.5 leading-6", className)} {...props} />
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
        "inline-flex h-11 items-center justify-center gap-2 rounded-[10px] px-5 text-[15px] font-semibold whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-[18px]",
        variant === "primary" && "bg-primary text-on-primary hover:bg-primary-hover",
        variant === "secondary" && "border border-line-strong bg-bg text-primary hover:bg-primary-soft",
        variant === "ghost" && "text-primary hover:bg-primary-soft",
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
      <label htmlFor={id} className="text-[14px] font-medium text-ink">
        {text}
        {required ? <span className="ml-0.5 text-required" aria-hidden> *</span> : null}
        {required ? <span className="sr-only"> (required)</span> : null}
      </label>
      {children({ id, "aria-invalid": Boolean(error), ...(describedBy ? { "aria-describedby": describedBy } : {}) })}
      {error ? (
        <p id={`${id}-error`} className="text-[13px] font-medium text-required">{error}</p>
      ) : help ? (
        <p id={`${id}-help`} className="text-[13px] text-label">{help}</p>
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
      className="inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-[13px] font-semibold whitespace-nowrap"
      style={{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {label(value)}
    </span>
  );
}

/** White card on the pale page. A border, not a shadow: cards sit on the page, nothing floats. */
export function Panel({ title, aside, children, className, id }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("scroll-mt-24 rounded-[16px] border border-line bg-bg", className)}>
      {title ? (
        <header className="flex flex-wrap items-center justify-between gap-3 px-6 pt-5 max-sm:px-4">
          <h2 className="text-[18px] font-bold text-ink">{title}</h2>
          {aside}
        </header>
      ) : null}
      <div className="px-6 py-5 max-sm:px-4">{children}</div>
    </section>
  );
}

export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,160px)_minmax(0,1fr)] gap-x-4 gap-y-3 text-[15px] max-sm:grid-cols-1 max-sm:gap-y-0.5">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-label max-sm:mt-2">{k}</dt>
          <dd className="min-w-0 font-medium break-words">{v || <span className="font-normal text-label">Not set</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Notice({ tone = "red", children }: { tone?: "red" | "green" | "amber" | "blue"; children: ReactNode }) {
  return (
    <p role={tone === "red" ? "alert" : "status"} className="rounded-[12px] px-4 py-3 text-[14px] font-medium" style={{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }}>
      {children}
    </p>
  );
}

/**
 * The booth tag: the portal's identity motif. Shaped like the hanging sign above a booth, it
 * carries the one fact every page here is about (which booth). Used on the home cards and heroes.
 */
export function BoothTag({ code, inverse }: { code: string | null | undefined; inverse?: boolean }) {
  if (!code) return null;
  return (
    <span
      className={cn(
        "relative inline-flex flex-col items-center rounded-[10px] px-3.5 pt-1.5 pb-2 leading-none",
        inverse ? "bg-bg text-primary" : "bg-primary text-on-primary",
      )}
    >
      <span className="absolute -top-1 size-2 rounded-full bg-accent" aria-hidden />
      <span className={cn("text-[10px] font-semibold tracking-wide", inverse ? "text-label" : "text-hero-muted")}>Booth</span>
      <span className="font-display text-[20px] font-extrabold">{code}</span>
    </span>
  );
}

/** Done of total as a bar; the number is the label, the bar only shows it at a glance. */
export function Progress({ done, total, label: text }: { done: number; total: number; label: string }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3 text-[14px]">
        <span className="font-semibold text-ink">{text}</span>
        <span className="font-semibold text-primary tabular-nums">{done} of {total} done</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-primary-soft" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label={text}>
        <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/**
 * Sign-in and password pages: the indigo side says what the portal is for (the three things an
 * exhibitor really does here), the white side holds the form. Stacks on phones, brand first.
 */
export function AuthLayout({ title, intro, children }: { title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid overflow-hidden rounded-[20px] border border-line bg-bg md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <div className="flex flex-col justify-between gap-8 bg-primary px-8 py-9 text-on-primary max-sm:px-5 max-sm:py-7">
        <div>
          <p className="text-[13px] font-semibold text-hero-muted">PERAGA Expo exhibitors</p>
          <p className="mt-2 font-display text-[26px] leading-[1.2] font-extrabold">Your booth, from contract to move-in.</p>
        </div>
        <ol className="flex flex-col gap-4 text-[15px]">
          {["Sign your booth contract", "Order services for your booth: power, furniture, internet, badges", "See what is paid and what is still due"].map((t, n) => (
            <li key={t} className="flex gap-3">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-bg font-display text-[14px] font-bold text-primary">{n + 1}</span>
              <span className="pt-0.5">{t}</span>
            </li>
          ))}
        </ol>
      </div>
      <div className="px-8 py-9 max-sm:px-5 max-sm:py-7">
        <h1 className="text-[26px] leading-tight font-extrabold text-ink">{title}</h1>
        {intro ? <div className="mt-2 text-[15px] text-muted">{intro}</div> : null}
        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}
