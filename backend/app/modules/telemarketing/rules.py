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
