# 06 Lead Assignment

Spec §6.1.

## Methods
- **Manual**: set Lead Owner on one lead.
- **Bulk**: select many leads in list view, assign to one agent.
- **Round robin**: select leads (or a filter result) + a set of agents; distribute evenly, continuing from the last agent used per edition/team.

Reassignment (lead already owned) needs `telemarketing.reassign`.

## Edition teams and assignment on import (owner decision 2026-10-25)
- An edition has teams (`edition_teams`), set on the Edition form by whoever has `edition.manage` (`GET`/`PUT /editions/{id}/teams`).
- An import can share its **new** leads round robin among the **recipients**: active members of those teams who hold `telemarketing.call` in the edition. Gate staff and other members without it get nothing. Example: 500 leads over 5 callers = 100 each.
- Opt-in per import (`auto_assign`); refused with 422 when there is no recipient. `GET /visitor-leads/imports/recipients?edition_id=` shows who would receive.
- The round robin cursor is per edition for imports (`pool_key = "import"`), so remainders carry over and several imports stay even. Recipients are read when the rows are done.
- History rows use method `IMPORT`; the job shows `assigned_count` and the count per person. Leads created by hand are not auto-assigned: they go through Assign To.

## Data
`lead_assignment_history`: `visitor_lead_id`, `from_user_id`, `to_user_id`, `method`, `actor_user_id`, `batch_id`, `assigned_at`. Never updated, never deleted. `visitor_leads.lead_owner_id` holds the current owner.

`round_robin_cursors`: `(edition_id, team_id)` to last agent position, updated with row lock.

## Tasks
- [ ] Tables + migration.
- [ ] `POST /visitor-leads/assignments` with body `{method, lead_ids | filter, agent_ids}`. Large batches go to the worker.
- [ ] Round-robin service with deterministic ordering and lock, so two managers running it at once do not double-assign.
- [ ] List view bulk action "Assign To", lead form "Assigned To" in the sidebar, assignment history in the activity timeline.
- [ ] Only agents in scope (same edition, team) are selectable.

## Acceptance criteria
- Every change creates a history row with actor and timestamp.
- Round robin over 10 leads and 3 agents gives 4/3/3, and the next run starts from the right agent.
- Agent without `telemarketing.reassign` gets 403 when changing an owned lead.
