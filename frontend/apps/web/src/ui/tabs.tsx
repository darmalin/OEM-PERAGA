import * as T from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Underline tabs, as in the screenshot's "Person" tab. */
export const Tabs = T.Root;

export function TabList({ tabs, className }: { tabs: { value: string; label: string }[]; className?: string }) {
  return (
    <T.List className={cn("flex gap-6 overflow-x-auto border-b border-line px-5 max-md:px-4", className)} aria-label="Sections">
      {tabs.map((t) => (
        <T.Trigger
          key={t.value}
          value={t.value}
          className="-mb-px h-11 border-b-2 border-transparent text-[13px] whitespace-nowrap text-label hover:text-ink data-[state=active]:border-ink data-[state=active]:font-medium data-[state=active]:text-ink"
        >
          {t.label}
        </T.Trigger>
      ))}
    </T.List>
  );
}

export function TabPanel({ value, children }: { value: string; children: ReactNode }) {
  return (
    <T.Content value={value} className="outline-none">
      {children}
    </T.Content>
  );
}
