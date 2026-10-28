import { useNavigate } from "@tanstack/react-router";
import { Command } from "cmdk";
import { Search } from "lucide-react";
import { useState } from "react";

import { can, useMe } from "@/lib/auth";

import type { PanelDef } from "./nav";

/** Ctrl+K: go to any page the user can open, or search leads (DESIGN.md). */
export function CommandBar({
  open,
  onOpenChange,
  panels,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  panels: PanelDef[];
}) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const me = useMe();
  const canSearchLeads = can(me, "visitor.read");
  const go = (to: string, search?: Record<string, string>) => {
    onOpenChange(false);
    setQuery("");
    void navigate({ to: to as "/", search: search as never });
  };
  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Search or go to a page"
      overlayClassName="fixed inset-0 z-50 bg-black/30"
      contentClassName="fixed top-[12vh] left-1/2 z-50 w-[min(560px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-[12px] border border-line bg-bg shadow-overlay"
    >
      <div className="flex items-center gap-2 border-b border-line px-4">
        <Search className="size-4 text-label" aria-hidden />
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Type a page name, or a lead's name, email, phone, or Registration ID"
          className="h-12 flex-1 bg-transparent text-[14px] outline-none placeholder:text-label"
        />
      </div>
      <Command.List className="max-h-[360px] overflow-y-auto p-2 text-[13px]">
        <Command.Empty className="px-3 py-6 text-center text-label">No page matches.</Command.Empty>
        {panels.map((p) => (
          <Command.Group
            key={p.id}
            heading={`${p.label} pages`}
            className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[12px] [&_[cmdk-group-heading]]:text-label"
          >
            {p.groups.flatMap((g) =>
              g.items.map((i) => (
                <Command.Item
                  key={`${p.id}${i.to}`}
                  value={`${p.label} ${g.label} ${i.label}`}
                  onSelect={() => go(i.to)}
                  className="flex h-9 cursor-pointer items-center gap-2 rounded-[8px] px-2 data-[selected=true]:bg-hover"
                >
                  <i.icon className="size-4 text-muted" strokeWidth={1.5} aria-hidden />
                  {i.label}
                  {g.label ? <span className="ml-auto text-[12px] text-label">{g.label}</span> : null}
                </Command.Item>
              )),
            )}
          </Command.Group>
        ))}
        {canSearchLeads && query.trim().length >= 2 ? (
          <Command.Group forceMount heading="Visitor Leads" className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[12px] [&_[cmdk-group-heading]]:text-label">
            <Command.Item
              // Neutral value + forceMount: always offered, never ranked above a matching page.
              value="__search-leads__"
              forceMount
              onSelect={() => go("/app/visitor-leads", { q: query.trim() })}
              className="flex h-9 cursor-pointer items-center gap-2 rounded-[8px] px-2 data-[selected=true]:bg-hover"
            >
              <Search className="size-4 text-muted" aria-hidden />
              Search leads for "{query.trim()}"
            </Command.Item>
          </Command.Group>
        ) : null}
      </Command.List>
    </Command.Dialog>
  );
}
