import { Link } from "@tanstack/react-router";
import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { usePageWidth } from "@/lib/layout";

import { EditionPicker } from "./edition-picker";

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  // Full width (the default) overrides a page's own max width, forms included.
  const full = usePageWidth() === "full";
  return <div className={cn("route-fade mx-auto w-full max-w-[1400px] px-6 pb-16 max-md:px-4", className, full && "max-w-none")}>{children}</div>;
}

interface PageHeadProps {
  title: ReactNode;
  meta?: ReactNode;
  indicators?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: string; params?: Record<string, string> };
  /** The page works in one edition: show the Exhibition Type picker before the actions. */
  edition?: boolean;
}

/** ENERGY 2 page head: 24px title, a meta line, indicators, one primary action. */
export function PageHead({ title, meta, indicators, actions, back, edition }: PageHeadProps) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 pt-6 pb-5">
      <div className="min-w-0">
        {back ? (
          <Link
            // Generic component: the caller passes a real route path.
            to={back.to as "/"}
            params={back.params as never}
            className="mb-2 inline-flex items-center gap-1 rounded-[6px] text-[13px] text-label hover:text-ink"
          >
            <ChevronLeft className="size-4" aria-hidden />
            {back.label}
          </Link>
        ) : null}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-[24px] leading-8 font-semibold tracking-[-0.01em] break-words">{title}</h1>
          {indicators}
        </div>
        {meta ? <div className="mt-1 text-[13px] text-label">{meta}</div> : null}
      </div>
      {actions || edition ? (
        <div className="flex flex-wrap items-center gap-2">
          {edition ? <EditionPicker /> : null}
          {actions}
        </div>
      ) : null}
    </header>
  );
}

/** White surface on the subtle page background; the form container in the screenshot. */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-[12px] border border-line bg-bg", className)}>{children}</section>
  );
}

export function PanelHeader({ title, actions }: { title: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3 max-md:px-4">
      <h2 className="text-[14px] font-semibold">{title}</h2>
      {actions}
    </div>
  );
}

export function FormActions({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line px-5 py-4 max-md:px-4">
      {children}
    </div>
  );
}

/** Read-only key/value list for detail sidebars. */
export function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,110px)_minmax(0,1fr)] gap-x-4 gap-y-2.5 text-[13px]">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-label">{k}</dt>
          <dd className="min-w-0 break-words text-ink">{v ?? <span className="text-label">Not set</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
