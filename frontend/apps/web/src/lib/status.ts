/** One color per status, everywhere (DESIGN.md "Status indicators"). */
export type Tone = "gray" | "blue" | "green" | "amber" | "red";

const TONES: Record<string, Tone> = {
  // telemarketing
  NEW: "gray",
  ANSWER: "blue",
  RECONTACTED: "blue",
  NO_ANSWER: "amber",
  RETRY_NO_ANSWER: "amber",
  // registration / qr
  NOT_REGISTERED: "gray",
  REGISTERED: "blue",
  CANCELLED: "gray",
  NONE: "gray",
  ACTIVE: "green",
  REVOKED: "red",
  // verification
  VALID: "green",
  INVALID: "red",
  UNDECIDED: "gray",
  ATTEND: "green",
  ATTEND_SOURCING: "green",
  UNDER_CONSIDERATION: "amber",
  NOT_ATTEND: "red",
  HANG_UP_IMMEDIATELY: "red",
  // jobs, email
  QUEUED: "blue",
  SENDING: "blue",
  RUNNING: "blue",
  SENT: "green",
  COMPLETED: "green",
  COMPLETED_WITH_ERRORS: "amber",
  FAILED: "red",
  EXPIRED: "gray",
  // gate
  FIRST_ENTRY: "green",
  REPEAT_ENTRY: "amber",
  PENDING: "amber",
  // editions, follow-ups
  DRAFT: "gray",
  CLOSED: "gray",
  ARCHIVED: "gray",
  OPEN: "blue",
  DONE: "green",
};

export function toneFor(status: string | null | undefined): Tone {
  if (!status) return "gray";
  if (status.startsWith("REJECTED_")) return "red";
  return TONES[status] ?? "gray";
}
