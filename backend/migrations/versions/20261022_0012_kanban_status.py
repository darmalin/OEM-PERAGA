"""kanban status rules: recompute telemarketing_status from call history

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-22

The 2026-10-22 rules change what a history means (No Answer then Answer is now ANSWER, not
RECONTACTED). Stored statuses are recomputed so they keep equalling the status function.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of telemarketing.rules at this revision; migrations never import app code.
_TRANSITIONS: dict[str, dict[bool, str]] = {
    "NEW": {True: "ANSWER", False: "NO_ANSWER"},
    "ANSWER": {True: "RECONTACTED"},
    "NO_ANSWER": {True: "ANSWER", False: "RETRY_NO_ANSWER"},
}


def _status(results: list[str]) -> str:
    status = "NEW"
    for r in results:
        status = _TRANSITIONS.get(status, {}).get(r == "ANSWER") or status
    return status


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT l.id, l.telemarketing_status, "
            "array_agg(c.call_result ORDER BY c.attempt_number) "
            "FROM visitor_leads l JOIN visitor_call_activities c ON c.visitor_lead_id = l.id "
            "GROUP BY l.id, l.telemarketing_status"
        )
    ).all()
    for lead_id, stored, results in rows:
        status = _status(list(results))
        if status != stored:
            conn.execute(
                sa.text(
                    "UPDATE visitor_leads SET telemarketing_status = :s, version = version + 1 "
                    "WHERE id = :id"
                ),
                {"s": status, "id": lead_id},
            )


def downgrade() -> None:
    """Statuses stay as recomputed; the old rule can be replayed by an older app if needed."""
