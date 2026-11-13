import type { Schemas } from "@ems/api";
import { useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { boothsQuery } from "@/features/exhibitors/queries";
import { cn } from "@/lib/cn";
import { formatMoney } from "@/lib/format";

export type Booth = Schemas["BoothOut"];

/** A listed booth, or a code typed in that becomes a new booth when saved. */
export type BoothChoice = { kind: "listed"; booth: Booth } | { kind: "new"; code: string };

/**
 * Search the free booths of an edition by code or hall, or type a code that is not in the list
 * (only for booth managers). The ARIA combobox pattern: arrows move, Enter picks, Escape closes.
 */
export function BoothPicker({
  editionId,
  canAdd,
  onPick,
  inputId,
  describedBy,
  addLabel = (code: string) => `Add booth “${code}”`,
  placeholder,
}: {
  editionId: string;
  canAdd: boolean;
  onPick: (choice: BoothChoice) => void;
  inputId?: string;
  describedBy?: string;
  /** Text of the option for a code not in the list. */
  addLabel?: (code: string) => string;
  placeholder?: string;
}) {
  const listId = useId();
  const [text, setText] = useState("");
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);

  // Search after a short pause, not on every key.
  useEffect(() => {
    const t = window.setTimeout(() => setTerm(text.trim()), 200);
    return () => window.clearTimeout(t);
  }, [text]);

  const found = useQuery({ ...boothsQuery(editionId, { available: true, q: term, page_size: 20 }), enabled: Boolean(editionId) && open });
  const typed = text.trim().toUpperCase();
  // The server search runs after the pause; filtering here keeps the list right while typing.
  const items = (found.data?.items ?? []).filter((b) => !typed || b.code.toUpperCase().includes(typed) || (b.hall ?? "").toUpperCase().includes(typed));
  const exact = items.some((b) => b.code.toUpperCase() === typed);
  const options: BoothChoice[] = [
    ...items.map((booth) => ({ kind: "listed" as const, booth })),
    ...(canAdd && typed && !exact ? [{ kind: "new" as const, code: text.trim() }] : []),
  ];

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (choice: BoothChoice) => {
    onPick(choice);
    setText("");
    setOpen(false);
  };

  return (
    <div ref={box} className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-label" aria-hidden />
        <input
          id={inputId}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-describedby={describedBy}
          aria-activedescendant={open && options[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          placeholder={placeholder ?? (canAdd ? "Search a booth code or hall, or type a new code" : "Search a booth code or hall")}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((i) => Math.min(i + 1, Math.max(options.length - 1, 0)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter" && open && options[active]) {
              e.preventDefault();
              pick(options[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          className="h-9 w-full rounded-[8px] border border-line bg-[var(--surface-input)] pr-3 pl-9 text-[14px] outline-none placeholder:text-label focus-visible:ring-2 focus-visible:ring-[var(--focus)]"
        />
      </div>
      {open ? (
        <ul id={listId} role="listbox" aria-label="Booths" className="absolute z-20 mt-1 max-h-[320px] w-full overflow-auto rounded-[8px] border border-line bg-bg py-1 shadow-lg">
          {found.isPending ? <li className="px-3 py-2 text-[13px] text-label">Searching</li> : null}
          {!found.isPending && options.length === 0 ? (
            <li className="px-3 py-2 text-[13px] text-label">{typed ? "No free booth matches." : "No booth is free in this edition."}</li>
          ) : null}
          {options.map((o, i) => (
            <li
              key={o.kind === "listed" ? o.booth.id : `new-${o.code}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(o);
              }}
              className={cn("flex cursor-pointer items-center gap-3 px-3 py-2 text-[13px]", i === active && "bg-subtle")}
            >
              {o.kind === "listed" ? (
                <>
                  <span className="w-16 shrink-0 font-medium tabular">{o.booth.code}</span>
                  <span className="min-w-0 flex-1 truncate text-muted">{[o.booth.hall, `${Number(o.booth.area_sqm)} m²`].filter(Boolean).join(" · ")}</span>
                  <span className="shrink-0 text-muted tabular">{formatMoney(o.booth.price, o.booth.currency)}</span>
                </>
              ) : (
                <span className="flex items-center gap-2 font-medium">
                  <Plus className="size-4" aria-hidden />
                  {addLabel(o.code)}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
