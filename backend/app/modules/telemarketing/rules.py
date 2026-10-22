"""Pure telemarketing rules."""

import uuid
from enum import StrEnum


class AssignmentMethod(StrEnum):
    MANUAL = "MANUAL"
    BULK = "BULK"
    ROUND_ROBIN = "ROUND_ROBIN"


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


# Kanban moves (owner decision 2026-10-22): the status after one more call, by whether it was
# answered. RECONTACTED and RETRY_NO_ANSWER are final: no further call is accepted.
TRANSITIONS: dict[str, dict[bool, str]] = {
    "NEW": {True: "ANSWER", False: "NO_ANSWER"},
    "ANSWER": {True: "RECONTACTED"},
    "NO_ANSWER": {True: "ANSWER", False: "RETRY_NO_ANSWER"},
}


def is_answered(call_result: str) -> bool:
    """Only ANSWER counts as answered; any other configured result counts as not answered."""
    return call_result == CallResult.ANSWER


def next_status(current: str, answered: bool) -> str | None:
    """Status after one more call, or None when the move is not allowed."""
    return TRANSITIONS.get(current, {}).get(answered)


def telemarketing_status(results: list[str]) -> str:
    """Derive the status from the attempt history (oldest first) by replaying the transitions.

    History written before the 2026-10-22 rules may contain moves that are no longer allowed;
    such a step leaves the status unchanged, so the result is defined for every history.
    """
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


def call_verification_errors(
    answered: bool, quality: LeadQuality, attend: str | None
) -> dict[str, str]:
    """Verification required with every call: an answered call needs Valid and Attend."""
    errors: dict[str, str] = {}
    if answered and quality != LeadQuality.VALID:
        errors["lead_quality"] = "An answered call needs Lead Quality Valid."
    if answered and attend is None:
        errors["attend"] = "Attend is required for an answered call."
    return errors


def allowed_call_results(extra: list[str]) -> list[str]:
    return [CallResult.ANSWER.value, CallResult.NO_ANSWER.value, *extra]
