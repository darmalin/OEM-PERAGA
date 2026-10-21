import { api } from "@ems/api";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { Check, ChevronsUpDown, LogOut, Menu as MenuIcon, Monitor, Moon, Search, Sun, X } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { useMe } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useEdition } from "@/lib/edition";
import { setTheme, type Theme, useTheme } from "@/lib/theme";
import { Button } from "@/ui/button";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuRadioGroup, MenuRadioItem, MenuSeparator, MenuTrigger } from "@/ui/menu";

import { CommandBar } from "./command-bar";
import { type PanelDef, visiblePanels } from "./nav";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

function isActive(path: string, to: string, home: string): boolean {
  return to === home ? path === to : path === to || path.startsWith(`${to}/`);
}

function Sidebar({ panel, panels, onNavigate }: { panel: PanelDef; panels: PanelDef[]; onNavigate?: () => void }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav aria-label={`${panel.label} navigation`} className="flex h-full flex-col gap-1 overflow-y-auto px-3 py-4">
      {panels.length > 1 ? (
        <div className="mb-3 grid grid-flow-col gap-1 rounded-[8px] bg-input p-1" role="group" aria-label="Panel">
          {panels.map((p) => (
            <Link
              key={p.id}
              to={p.home as "/"}
              onClick={onNavigate}
              aria-current={p.id === panel.id ? "page" : undefined}
              className={cn(
                "flex h-7 items-center justify-center rounded-[6px] text-[12px] font-medium text-label hover:text-ink pointer-coarse:h-10",
                p.id === panel.id && "bg-bg text-ink shadow-[0_1px_2px_rgb(0_0_0/0.08)]",
              )}
            >
              {p.label}
            </Link>
          ))}
        </div>
      ) : null}
      {panel.groups.map((g) => (
        <div key={g.label || "top"} className="mb-2">
          {g.label ? <p className="px-2 pt-2 pb-1 text-[12px] font-medium text-label">{g.label}</p> : null}
          <ul className="flex flex-col gap-0.5">
            {g.items.map((item) => {
              const active = isActive(path, item.to, panel.home);
              return (
                <li key={item.to}>
                  <Link
                    to={item.to as "/"}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex h-8 items-center gap-2.5 rounded-[8px] px-2 text-[13px] text-muted hover:bg-hover hover:text-ink pointer-coarse:h-11",
                      active && "bg-bg font-medium text-ink shadow-[0_1px_2px_rgb(0_0_0/0.08)] hover:bg-bg",
                    )}
                  >
                    <item.icon className="size-4 shrink-0" strokeWidth={1.5} aria-hidden />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function EditionSwitcher() {
  const { edition, editions, setEditionId } = useEdition();
  const queryClient = useQueryClient();
  if (!edition) return <span className="text-[13px] text-label">No edition</span>;
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button variant="ghost" className="max-w-[240px] gap-2 px-2" aria-label={`Edition: ${edition.name}. Change edition`}>
          <span className="truncate font-semibold tabular">{edition.code}</span>
          <span className="truncate text-label max-lg:hidden">{edition.name}</span>
          <ChevronsUpDown className="text-label" aria-hidden />
        </Button>
      </MenuTrigger>
      <MenuContent align="start">
        <MenuLabel>Edition</MenuLabel>
        {editions.map((e) => (
          <MenuItem
            key={e.id}
            onSelect={() => {
              setEditionId(e.id);
              void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "auth" });
            }}
          >
            <span className="w-24 font-medium tabular">{e.code}</span>
            <span className="flex-1 truncate text-muted">{e.name}</span>
            {e.id === edition.id ? <Check aria-label="Current edition" /> : null}
          </MenuItem>
        ))}
      </MenuContent>
    </Menu>
  );
}

function UserMenu() {
  const me = useMe();
  const theme = useTheme();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const signOut = async () => {
    await api.POST("/api/v1/auth/logout");
    queryClient.clear();
    await navigate({ to: "/login" });
  };
  return (
    <Menu>
      <MenuTrigger asChild>
        <button
          className="grid size-8 place-items-center rounded-full bg-input text-[12px] font-semibold text-ink hover:bg-hover pointer-coarse:size-11"
          aria-label={`Account menu for ${me.user.full_name}`}
        >
          {initials(me.user.full_name)}
        </button>
      </MenuTrigger>
      <MenuContent>
        <div className="px-2 py-2">
          <p className="text-[13px] font-medium">{me.user.full_name}</p>
          <p className="text-[12px] text-label">{me.user.email}</p>
        </div>
        <MenuSeparator />
        <MenuLabel>Theme</MenuLabel>
        <MenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as Theme)}>
          <MenuRadioItem value="light">
            <span className="flex items-center gap-2"><Sun className="size-4 text-muted" aria-hidden />Light</span>
          </MenuRadioItem>
          <MenuRadioItem value="dark">
            <span className="flex items-center gap-2"><Moon className="size-4 text-muted" aria-hidden />Dark</span>
          </MenuRadioItem>
          <MenuRadioItem value="system">
            <span className="flex items-center gap-2"><Monitor className="size-4 text-muted" aria-hidden />System</span>
          </MenuRadioItem>
        </MenuRadioGroup>
        <MenuSeparator />
        <MenuItem onSelect={() => void signOut()}>
          <LogOut aria-hidden />
          Sign Out
        </MenuItem>
      </MenuContent>
    </Menu>
  );
}

export function Shell({ panelId, children }: { panelId: PanelDef["id"]; children: ReactNode }) {
  const me = useMe();
  const panels = visiblePanels(me);
  const panel = panels.find((p) => p.id === panelId);
  const [drawer, setDrawer] = useState(false);
  const [command, setCommand] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommand((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-[8px] focus:bg-bg focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-line bg-bg px-3">
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setDrawer(true)} aria-label="Open navigation">
          <MenuIcon aria-hidden />
        </Button>
        {/* [LOGO] placeholder: product name as text until the owner supplies a logo (R-23). */}
        <Link to="/" className="rounded-[6px] px-2 text-[15px] font-bold tracking-[-0.02em]">
          EMS
        </Link>
        <span className="h-5 w-px bg-line max-sm:hidden" aria-hidden />
        <div className="max-sm:hidden">
          <EditionSwitcher />
        </div>
        <div className="flex-1" />
        <Button
          variant="secondary"
          className="w-[280px] justify-start gap-2 text-label max-md:w-auto max-md:px-2"
          onClick={() => setCommand(true)}
          aria-label="Search or go to a page (Ctrl+K)"
        >
          <Search aria-hidden />
          <span className="max-md:hidden">Search or go to</span>
          <kbd className="ml-auto rounded-[4px] border border-line px-1.5 text-[11px] text-label max-md:hidden">Ctrl K</kbd>
        </Button>
        <UserMenu />
      </header>
      <div className="flex flex-1">
        {panel ? (
          <aside className="sticky top-12 h-[calc(100dvh-48px)] w-[232px] shrink-0 border-r border-line bg-subtle max-lg:hidden">
            <Sidebar panel={panel} panels={panels} />
          </aside>
        ) : null}
        <main id="main" className="min-w-0 flex-1">
          {children}
        </main>
      </div>
      {drawer && panel ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 bg-black/40" aria-label="Close navigation" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-[280px] flex-col bg-subtle shadow-overlay">
            <div className="flex h-12 items-center justify-between border-b border-line px-3">
              <EditionSwitcher />
              <Button variant="ghost" size="icon" onClick={() => setDrawer(false)} aria-label="Close navigation">
                <X aria-hidden />
              </Button>
            </div>
            <Sidebar panel={panel} panels={panels} onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      ) : null}
      <CommandBar open={command} onOpenChange={setCommand} panels={panels} />
    </div>
  );
}
