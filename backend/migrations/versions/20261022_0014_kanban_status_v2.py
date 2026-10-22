"""kanban status table v2: recompute telemarketing_status from call history

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-22

Second owner decision of 2026-10-22: No Answer and Retry No Answer move to RECONTACTED when
answered, and calls that do not move the lead are accepted. Stored statuses are recomputed so
they keep equalling the status function.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of telemarketing.rules at this revision; migrations never import app code.
_TRANSITIONS: dict[str, dict[bool, str]] = {
    "NEW": {True: "ANSWER", False: "NO_ANSWER"},
    "ANSWER": {True: "RECONTACTED", False: "ANSWER"},
    "NO_ANSWER": {True: "RECONTACTED", False: "RETRY_NO_ANSWER"},
    "RETRY_NO_ANSWER": {True: "RECONTACTED", False: "RETRY_NO_ANSWER"},
    "RECONTACTED": {True: "RECONTACTED", False: "RECONTACTED"},
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
