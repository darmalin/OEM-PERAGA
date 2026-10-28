import type { Schemas } from "@ems/api";

export type TmStatus = Schemas["LeadOut"]["telemarketing_status"];

/**
 * Status after one more call (FEATURES/07, owner decisions 2026-10-28), mirrored from backend
 * telemarketing/rules.py for the UI only. Every call is accepted; some leave the status as is.
 */
const TRANSITIONS: Record<TmStatus, { answered: TmStatus; unanswered: TmStatus }> = {
  NEW: { answered: "ANSWER", unanswered: "NO_ANSWER" },
  ANSWER: { answered: "RECONTACTED", unanswered: "RETRY_NO_ANSWER" },
  NO_ANSWER: { answered: "RECONTACTED", unanswered: "RETRY_NO_ANSWER" },
  RETRY_NO_ANSWER: { answered: "RECONTACTED", unanswered: "RETRY_NO_ANSWER" },
  RECONTACTED: { answered: "RECONTACTED", unanswered: "RECONTACTED" },
};

/** Never reached: verification takes Lead Quality only (Attend, B2B, buyer type disabled). */
export const UNREACHED: ReadonlySet<TmStatus> = new Set(["NO_ANSWER", "RETRY_NO_ANSWER"]);

export const BOARD_COLUMNS: TmStatus[] = ["NEW", "ANSWER", "NO_ANSWER", "RECONTACTED", "RETRY_NO_ANSWER"];

export function nextStatus(current: TmStatus, answered: boolean): TmStatus {
  return TRANSITIONS[current][answered ? "answered" : "unanswered"];
}

/** Both outcomes of a call on a lead in `current`; `moves` is false when the status stays. */
export function outcomes(current: TmStatus): { answered: boolean; to: TmStatus; moves: boolean }[] {
  return ([true, false] as const).map((answered) => {
    const to = nextStatus(current, answered);
    return { answered, to, moves: to !== current };
  });
}

/** Columns a card in `current` can be moved to on the board. */
export function moves(current: TmStatus): { to: TmStatus; answered: boolean }[] {
  return outcomes(current).filter((o) => o.moves);
}
