import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark" | "system";
const KEY = "ems.theme";
const listeners = new Set<() => void>();

function read(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

function apply(theme: Theme): void {
  const dark =
    theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* not persisted in private mode */
  }
  apply(theme);
  listeners.forEach((l) => l());
}

export function watchSystemTheme(): void {
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => apply(read()));
}

export function useTheme(): Theme {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    read,
    () => "system",
  );
}
