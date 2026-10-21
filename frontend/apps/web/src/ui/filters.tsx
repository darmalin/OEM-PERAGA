import { Search, X } from "lucide-react";
import { type ReactNode, useEffect, useId, useState } from "react";

import { cn } from "@/lib/cn";

import { Button } from "./button";
import { Input, Select } from "./input";

export function FilterBar({ children, onClear, active }: { children: ReactNode; onClear?: () => void; active?: boolean }) {
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-line px-4 py-3" role="search">
      {children}
      {onClear && active ? (
        <Button variant="ghost" size="sm" onClick={onClear} className="mb-0.5">
          <X aria-hidden />
          Clear Filters
        </Button>
      ) : null}
    </div>
  );
}

/** Search box that writes to the URL after the user pauses typing. */
export function SearchFilter({ value, onChange, placeholder, label = "Search" }: { value: string | undefined; onChange: (v: string | undefined) => void; placeholder: string; label?: string }) {
  const [text, setText] = useState(value ?? "");
  const [synced, setSynced] = useState(value);
  const id = useId();
  // The URL changed from outside (Clear Filters, back button): show its value.
  if (value !== synced) {
    setSynced(value);
    setText(value ?? "");
  }
  useEffect(() => {
    const t = setTimeout(() => {
      const next = text.trim() || undefined;
      if (next !== (value ?? undefined)) onChange(next);
    }, 350);
    return () => clearTimeout(t);
  }, [text, value, onChange]);
  return (
    <div className="relative min-w-[220px] flex-1 max-sm:min-w-full">
      <label htmlFor={id} className="sr-only">{label}</label>
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-label" aria-hidden />
      <Input id={id} value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} className="pl-8" type="search" />
    </div>
  );
}

export function SelectFilter({
  label,
  value,
  onChange,
  options,
  allLabel = "All",
  className,
}: {
  label: string;
  value: string | undefined;
  onChange: (v: string | undefined) => void;
  options: { value: string; label: string }[];
  allLabel?: string;
  className?: string;
}) {
  const id = useId();
  return (
    <div className={cn("flex min-w-[150px] flex-col gap-1 max-sm:flex-1", className)}>
      <label htmlFor={id} className="text-[12px] text-label">{label}</label>
      <Select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || undefined)}>
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </Select>
    </div>
  );
}

export function DateFilter({ label, value, onChange }: { label: string; value: string | undefined; onChange: (v: string | undefined) => void }) {
  const id = useId();
  return (
    <div className="flex min-w-[150px] flex-col gap-1 max-sm:flex-1">
      <label htmlFor={id} className="text-[12px] text-label">{label}</label>
      <Input id={id} type="date" value={value ?? ""} onChange={(e) => onChange(e.target.value || undefined)} />
    </div>
  );
}
