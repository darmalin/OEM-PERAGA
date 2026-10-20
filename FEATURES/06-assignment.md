# 06 Lead Assignment

Spec §6.1.

## Methods
- **Manual**: set Lead Owner on one lead.
- **Bulk**: select many leads in list view, assign to one agent.
- **Round robin**: select leads (or a filter result) + a set of agents; distribute evenly, continuing from the last agent used per edition/team.

Reassignment (lead already owned) needs `telemarketing.reassign`.

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
