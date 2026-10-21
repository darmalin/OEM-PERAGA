import { useSyncExternalStore } from "react";

import type { DeviceContext } from "./db";

export type Phase = "loading" | "activate" | "ready" | "gone";
/** Header indicator: Online, Offline, or Sync error (DESIGN.md "Scanner"). */
export type Link = "online" | "offline" | "error";

export interface ScannerState {
  phase: Phase;
  device: DeviceContext | null;
  link: Link;
  /** Message of the last failed sync or refresh that was not a network failure. */
  error: string | null;
  /** Shown on the "gone" screen: why the device can no longer scan. */
  goneMessage: string | null;
  syncing: boolean;
}

let state: ScannerState = {
  phase: "loading",
  device: null,
  link: typeof navigator !== "undefined" && !navigator.onLine ? "offline" : "online",
  error: null,
  goneMessage: null,
  syncing: false,
};
const listeners = new Set<() => void>();

export function getState(): ScannerState {
  return state;
}

export function setState(patch: Partial<ScannerState>): void {
  state = { ...state, ...patch };
  for (const l of listeners) l();
}

function subscribe(l: () => void): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useScanner(): ScannerState {
  return useSyncExternalStore(subscribe, getState, getState);
}
