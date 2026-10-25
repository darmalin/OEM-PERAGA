import { useSyncExternalStore } from "react";

/** Page width, per browser. Full width by default (owner request 2026-10-25). */
export type PageWidth = "full" | "centered";
const KEY = "ems.page-width";
const listeners = new Set<() => void>();

function read(): PageWidth {
  try {
    return localStorage.getItem(KEY) === "centered" ? "centered" : "full";
  } catch {
    return "full";
  }
}

export function setPageWidth(width: PageWidth): void {
  try {
    localStorage.setItem(KEY, width);
  } catch {
    /* not persisted in private mode */
  }
  listeners.forEach((l) => l());
}

export function usePageWidth(): PageWidth {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    read,
    () => "full",
  );
}
