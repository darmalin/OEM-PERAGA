"""Pure telemarketing rules."""

import uuid
from enum import StrEnum


class AssignmentMethod(StrEnum):
    MANUAL = "MANUAL"
    BULK = "BULK"
    ROUND_ROBIN = "ROUND_ROBIN"
    IMPORT = "IMPORT"  # round robin over the edition's teams when an import finishes


def round_robin(
    lead_ids: list[uuid.UUID], agent_ids: list[uuid.UUID], last_agent_id: uuid.UUID | None
) -> tuple[list[tuple[uuid.UUID, uuid.UUID]], uuid.UUID | None]:
    """Distribute leads over agents in a stable order, continuing after the last agent used.

    Agents are ordered by ID so the result does not depend on request order. If the last agent
    is no longer in the pool, the next one in ID order takes over.
    """
    if not lead_ids or not agent_ids:
        return [], last_agent_id
    agents = sorted(set(agent_ids))
    if last_agent_id is None:
        start = 0
    elif last_agent_id in agents:
        start = agents.index(last_agent_id) + 1
    else:
        start = next((i for i, a in enumerate(agents) if a > last_agent_id), 0)
    pairs = [(lead, agents[(start + i) % len(agents)]) for i, lead in enumerate(lead_ids)]
    return pairs, pairs[-1][1]


class CallResult(StrEnum):
    """D7: Answer / No Answer by default; extra results come from EMS_CALL_RESULTS_EXTRA."""

    ANSWER = "ANSWER"
    NO_ANSWER = "NO_ANSWER"


class FollowupStatus(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class FollowupAction(StrEnum):
    CREATE = "CREATE"
    RESCHEDULE = "RESCHEDULE"
    DONE = "DONE"
    CANCEL = "CANCEL"


# Telemarketing status after one more call, by whether it was answered (owner decisions
# 2026-10-22, FEATURES/07). Every call is accepted; some leave the status as it is: a visitor
# who was reached stays reached, and a lead that keeps not answering stays in RETRY_NO_ANSWER.
TRANSITIONS: dict[str, dict[bool, str]] = {
    "NEW": {True: "ANSWER", False: "NO_ANSWER"},
    "ANSWER": {True: "RECONTACTED", False: "ANSWER"},
    "NO_ANSWER": {True: "RECONTACTED", False: "RETRY_NO_ANSWER"},
    "RETRY_NO_ANSWER": {True: "RECONTACTED", False: "RETRY_NO_ANSWER"},
    "RECONTACTED": {True: "RECONTACTED", False: "RECONTACTED"},
}


def is_answered(call_result: str) -> bool:
    """Only ANSWER counts as answered; any other configured result counts as not answered."""
    return call_result == CallResult.ANSWER


def next_status(current: str, answered: bool) -> str | None:
    """Status after one more call; None only for a status outside the table."""
    return TRANSITIONS.get(current, {}).get(answered)


def telemarketing_status(results: list[str]) -> str:
    """Derive the status from the attempt history (oldest first) by replaying the table."""
    status = "NEW"
    for result in results:
        status = next_status(status, is_answered(result)) or status
    return status


class LeadQuality(StrEnum):
    """Verification "Lead Quality": whether the phone or email reached a real visitor."""

    VALID = "VALID"
    INVALID = "INVALID"
    UNDECIDED = "UNDECIDED"


def quality_flags(quality: LeadQuality) -> dict[str, bool]:
    """Lead Quality as the two stored flags (Valid Lead / Invalid, never both)."""
    return {
        "is_valid_lead": quality == LeadQuality.VALID,
        "is_invalid": quality == LeadQuality.INVALID,
    }


# Verification fields that only mean something after a conversation.
ANSWERED_ONLY_FIELDS = ("attend", "b2b_matching", "buyer_type")
# Statuses where the visitor has never been reached: only Lead Quality may be set.
UNREACHED = frozenset({"NO_ANSWER", "RETRY_NO_ANSWER"})


def call_verification_errors(
    answered: bool,
    moves: bool,
    quality: LeadQuality | None,
    attend: str | None,
    answered_only_sent: list[str],
) -> dict[str, str]:
    """Verification sent with a call (FEATURES/07).

    Answered: Lead Quality Valid and Attend are required. Not answered: only Lead Quality, and
    only required when the call moves the lead to another status.
    """
    errors: dict[str, str] = {}
    if answered:
        if quality != LeadQuality.VALID:
            errors["lead_quality"] = "An answered call needs Lead Quality Valid."
        if attend is None:
            errors["attend"] = "Attend is required for an answered call."
        return errors
    if moves and quality is None:
        errors["lead_quality"] = "Lead Quality is required."
    for field in answered_only_sent:
        errors[field] = "Not used when the call was not answered."
    return errors


def allowed_call_results(extra: list[str]) -> list[str]:
    return [CallResult.ANSWER.value, CallResult.NO_ANSWER.value, *extra]
