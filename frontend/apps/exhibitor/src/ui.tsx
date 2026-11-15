import { cn } from "@ems/ui/cn";
import { Loader2 } from "lucide-react";
import { type ButtonHTMLAttributes, forwardRef, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes, useId } from "react";

import { label, toneOf } from "./lib";

// Portal look (styles.css), after the old exhibitor manual: white cards with a grey title bar on a
// light grey page, the show's colour on actions and the active menu item, near-black table heads.
const control =
  "w-full rounded-[8px] border border-line-strong bg-bg px-3.5 text-[15px] text-ink placeholder:text-label hover:border-primary/50 disabled:cursor-not-allowed disabled:bg-subtle disabled:text-muted aria-[invalid=true]:border-[var(--required)]";

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
        "inline-flex h-11 items-center justify-center gap-2 rounded-[8px] px-5 text-[15px] font-semibold whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-[18px]",
        variant === "primary" && "bg-primary text-on-primary hover:bg-primary-hover",
        variant === "secondary" && "border border-line-strong bg-bg text-ink hover:border-primary/50 hover:text-primary",
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
      <label htmlFor={id} className="text-[14px] font-semibold text-ink">
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

/**
 * White band under the menu with the page title, as on every inner page of the old manual. The
 * aside (a deadline, a count) sits on the right and drops below the title on phones.
 */
export function PageHead({ title, subtitle, aside, children }: { title: ReactNode; subtitle?: ReactNode; aside?: ReactNode; children?: ReactNode }) {
  return (
    <div className="border-b border-line bg-bg">
      <div className="mx-auto flex max-w-[1280px] flex-wrap items-start justify-between gap-4 px-6 py-8 max-sm:px-4 max-sm:py-6">
        <div className="min-w-0">
          {children}
          <h1 className="text-[32px] leading-tight font-bold text-ink max-sm:text-[26px]">{title}</h1>
          {subtitle ? <p className="mt-1.5 text-[14px] text-label">{subtitle}</p> : null}
        </div>
        {aside}
      </div>
    </div>
  );
}

/** The grey area under the page head that holds the cards. */
export function PageBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto flex w-full max-w-[1280px] flex-col gap-6 px-6 py-8 max-sm:px-4 max-sm:py-6", className)}>{children}</div>;
}

/** Grey title bar, as the section heads of the old manual ("Company Information", "A. Lighting"). */
export function Band({ children, aside, as: Tag = "h2" }: { children: ReactNode; aside?: ReactNode; as?: "h2" | "h3" }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[8px] bg-band px-4 py-2.5">
      <Tag className="text-[17px] font-bold text-ink">{children}</Tag>
      {aside}
    </div>
  );
}

/** White card on the grey page; its title is a grey bar inside, as in the old manual. */
export function Panel({ title, aside, children, className, id }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("scroll-mt-24 rounded-[12px] border border-line bg-bg p-6 max-sm:p-4", className)}>
      {title ? <div className="mb-5"><Band aside={aside}>{title}</Band></div> : null}
      {children}
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

/** Label on the left, the value in a grey read-only box: the old "Company Information" block. */
export function ReadonlyRows({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,2fr)] items-center gap-x-6 gap-y-3 text-[14px] max-sm:grid-cols-1 max-sm:gap-y-1">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-semibold text-ink max-sm:mt-2">{k}</dt>
          <dd className="min-h-10 min-w-0 rounded-[8px] border border-line bg-subtle px-3.5 py-2 break-words">{v || <span className="text-label">Not set</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Notice({ tone = "red", children }: { tone?: "red" | "green" | "amber" | "blue"; children: ReactNode }) {
  return (
    <p role={tone === "red" ? "alert" : "status"} className="rounded-[8px] px-4 py-3 text-[14px] font-medium" style={{ color: `var(--${tone}-fg)`, background: `var(--${tone}-bg)` }}>
      {children}
    </p>
  );
}

/** Done of total as a thin bar with "2 / 13" beside it, as on the old home page. */
export function Progress({ done, total, label: text }: { done: number; total: number; label: string }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div className="flex items-center gap-4">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-subtle" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label={text}>
        <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[14px] font-semibold text-ink tabular-nums">{done} / {total}</span>
    </div>
  );
}

const SHOW_LOGOS = [
  { src: "brand/indo-intertex-logo.png", alt: "Indo Intertex", width: 125, height: 32 },
  { src: "brand/inatex-logo.png", alt: "INATEX", width: 122, height: 32 },
];

/**
 * Sign-in and password pages, as the old manual's: a photo of a show floor behind a frosted card,
 * the shows' logos and a welcome on the left, the form on the right. Stacks on phones.
 */
export function AuthLayout({ title, intro, children }: { title: string; intro?: ReactNode; children: ReactNode }) {
  return (
    <div
      className="flex min-h-dvh items-center justify-center bg-cover bg-center px-4 py-8"
      style={{ backgroundImage: `url(${import.meta.env.BASE_URL}brand/login-bg.jpg)` }}
    >
      <div className="grid w-full max-w-[1360px] overflow-hidden rounded-[24px] bg-bg/75 backdrop-blur-xl md:min-h-[min(820px,calc(100dvh-64px))] md:grid-cols-2">
        <div className="flex flex-col items-center justify-center gap-6 px-8 py-10 text-center max-sm:px-5 max-sm:py-8">
          <div className="flex items-center gap-5">
            {SHOW_LOGOS.map((l, n) => (
              <img key={l.alt} src={`${import.meta.env.BASE_URL}${l.src}`} alt={l.alt} width={l.width} height={l.height}
                className={cn("h-11 w-auto max-sm:h-8", n > 0 && "border-l border-line-strong pl-5")} />
            ))}
          </div>
          <div className="w-full max-w-[380px] border-t border-line-strong pt-6">
            <p className="text-[24px] font-bold text-ink">Welcome Back!</p>
            <p className="mt-3 text-[15px] text-ink">Sign in to your account to set up your booth, order services, and follow your payments.</p>
            <p className="mt-6 text-[13px] text-muted">PERAGA Expo · Online Exhibitor Manual</p>
          </div>
        </div>
        <div className="flex items-center justify-center bg-bg/60 px-8 py-10 max-sm:px-5 max-sm:py-8">
          <div className="w-full max-w-[450px]">
            <h1 className="text-[30px] leading-tight font-bold text-ink">{title}</h1>
            {intro ? <div className="mt-1.5 text-[15px] text-muted">{intro}</div> : null}
            <div className="mt-7">{children}</div>
            <p className="mt-6 text-center text-[13px] text-muted">© {new Date().getFullYear()} PERAGA Expo. All rights reserved.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
