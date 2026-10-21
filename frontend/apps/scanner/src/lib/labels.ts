import type { ScanResult } from "./db";
import type { NoDecision } from "./decide";

/** The word on the result screen (DESIGN.md "Scanner"). */
export const RESULT_WORD: Record<ScanResult, string> = {
  FIRST_ENTRY: "FIRST ENTRY",
  REPEAT_ENTRY: "REPEAT ENTRY",
  REJECTED_UNKNOWN: "REJECTED",
  REJECTED_REVOKED: "REJECTED",
  REJECTED_WRONG_EDITION: "REJECTED",
  REJECTED_CANCELLED: "REJECTED",
};

export const REJECT_REASON: Partial<Record<ScanResult, string>> = {
  REJECTED_UNKNOWN: "Unknown code",
  REJECTED_REVOKED: "Revoked",
  REJECTED_WRONG_EDITION: "Other edition",
  REJECTED_CANCELLED: "Registration cancelled",
};

export const RESULT_LABEL: Record<ScanResult, string> = {
  FIRST_ENTRY: "First Entry",
  REPEAT_ENTRY: "Repeat Entry",
  REJECTED_UNKNOWN: "Rejected: Unknown code",
  REJECTED_REVOKED: "Rejected: Revoked",
  REJECTED_WRONG_EDITION: "Rejected: Other edition",
  REJECTED_CANCELLED: "Rejected: Registration cancelled",
};

export const NO_DECISION_REASON: Record<NoDecision, string> = {
  NO_CACHE: "No offline list on this device yet",
  CACHE_EXPIRED: "The offline list expired",
};

export type Tone = "first" | "repeat" | "rejected" | "neutral";

export function toneOf(result: ScanResult): Tone {
  if (result === "FIRST_ENTRY") return "first";
  if (result === "REPEAT_ENTRY") return "repeat";
  return "rejected";
}

/** A distinct vibration per result, so color is never the only signal. */
export const VIBRATION: Record<Tone, number[]> = {
  first: [150],
  repeat: [100, 100, 100],
  rejected: [500, 150, 500],
  neutral: [300, 100, 300, 100, 300],
};
