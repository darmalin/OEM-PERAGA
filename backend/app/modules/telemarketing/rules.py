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


def telemarketing_status(results: list[str]) -> str:
    """spec 6.2: derive the status from the attempt history (oldest first).

    Only ANSWER counts as answered; any other configured result counts as not answered.
    """
    if not results:
        return "NEW"
    answered = results[-1] == CallResult.ANSWER
    if len(results) == 1:
        return "ANSWER" if answered else "NO_ANSWER"
    return "RECONTACTED" if answered else "RETRY_NO_ANSWER"


def allowed_call_results(extra: list[str]) -> list[str]:
    return [CallResult.ANSWER.value, CallResult.NO_ANSWER.value, *extra]
