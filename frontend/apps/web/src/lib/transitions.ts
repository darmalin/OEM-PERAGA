import type { Schemas } from "@ems/api";

export type TmStatus = Schemas["LeadOut"]["telemarketing_status"];

/**
 * Kanban moves (owner decision 2026-10-22), mirrored from backend telemarketing/rules.py for the
 * UI only: the API refuses any other move. RECONTACTED and RETRY_NO_ANSWER are final.
 */
const TRANSITIONS: Partial<Record<TmStatus, Partial<Record<"answered" | "unanswered", TmStatus>>>> = {
  NEW: { answered: "ANSWER", unanswered: "NO_ANSWER" },
  ANSWER: { answered: "RECONTACTED" },
  NO_ANSWER: { answered: "ANSWER", unanswered: "RETRY_NO_ANSWER" },
};

export const BOARD_COLUMNS: TmStatus[] = ["NEW", "ANSWER", "NO_ANSWER", "RECONTACTED", "RETRY_NO_ANSWER"];

export function nextStatus(current: TmStatus, answered: boolean): TmStatus | undefined {
  return TRANSITIONS[current]?.[answered ? "answered" : "unanswered"];
}

/** Columns a card in `current` may move to, with whether the call was answered. */
export function moves(current: TmStatus): { to: TmStatus; answered: boolean }[] {
  return ([true, false] as const).flatMap((answered) => {
    const to = nextStatus(current, answered);
    return to ? [{ to, answered }] : [];
  });
}

export function isFinal(status: TmStatus): boolean {
  return moves(status).length === 0;
}
