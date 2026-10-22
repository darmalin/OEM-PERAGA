# 07 Telemarketing: Calls, Verification, Follow-ups

Spec §6.2 to §6.5. Open decisions D3, D4, D7.

## Telemarketing status (derived, never typed in)

Owner decision 2026-10-22: the status is a kanban with fixed moves. Each move is one call.

| From | Answered call | Not answered call |
|---|---|---|
| `NEW` | `ANSWER` | `NO_ANSWER` |
| `ANSWER` | `RECONTACTED` | not allowed |
| `NO_ANSWER` | `ANSWER` | `RETRY_NO_ANSWER` |
| `RECONTACTED` | final | final |
| `RETRY_NO_ANSWER` | final | final |

- Stored on the lead, recomputed from `visitor_call_activities` by replaying the moves (`telemarketing.rules.telemarketing_status`). A move refused by the rules writes nothing and answers `409 STATUS_TRANSITION_NOT_ALLOWED`, checked under the lead row lock.
- History written before 2026-10-22 may hold moves that are no longer allowed; replaying skips them. Migration `0012` recomputed every stored status.
- Board: `/app/visitor-leads/board` (drag a card, or its Move menu). Both open the Log Call page with the target column.

## Call activity
`visitor_call_activities`: `id`, `visitor_lead_id`, `agent_id`, `attempt_number`, `call_result`, `called_at`, `duration_seconds`, `notes`, `next_followup_at`, `created_at`. No VoIP; agents log manually. `attempt_number` assigned under row lock on the lead.

Call results: `ANSWER`, `NO_ANSWER` by default; extra values only through config (D7).

## Verification
- Fields: Lead Quality (Valid / Invalid / Undecided, stored as the two mutually exclusive flags `is_valid_lead` / `is_invalid`), Attend (5 fixed values), B2B Matching, Type of Buyers (B-Side / C-Side).
- Lead Quality says whether the phone or email reached a real visitor.
- Every call (every kanban move) carries `verification` (owner decision 2026-10-22):
  - Answered (to `ANSWER` or `RECONTACTED`): Lead Quality must be Valid, Attend is required.
  - Not answered (to `NO_ANSWER` or `RETRY_NO_ANSWER`): any Lead Quality, Attend optional.
- The Verification tab still allows a partial save between calls (`PATCH /visitor-leads/{id}/verification`).
- `visitor_verifications` keeps history rows; lead holds the current values.
- `Hang Up Immediately` in Attend does not mean "not attending"; the call result is recorded separately.

## Follow-up
`visitor_followups`: `visitor_lead_id`, `assigned_to`, `due_at`, `status` (`OPEN`, `DONE`, `CANCELLED`), `created_from_call_id`, history of reschedules.

## Tasks
- [ ] Tables, constraints, status function + tests.
- [ ] `POST /visitor-leads/{id}/calls`, `PATCH /visitor-leads/{id}/verification`, `POST /visitor-leads/{id}/followups`, `PATCH /followups/{id}` (reschedule, done, cancel).
- [ ] "My Calls" queue for agents: assigned leads ordered by follow-up due, then `NEW`.
- [ ] "Log Call" dialog on the lead form: result, notes, optional next follow-up. Verification section editable when the last result is Answer.
- [ ] Follow-ups list: Today, Overdue, Upcoming tabs.
- [ ] Manager view (`telemarketing.view_team`): team queue, filter by agent.
- [ ] Email reminder job (Celery Beat) behind D4; idempotency key `followup:{id}:{due_at}` so a reminder is never sent twice.
- [ ] Audit everything.

## Acceptance criteria
- Two agents logging a call on the same lead at once get attempt numbers 1 and 2, not 1 and 1.
- Status always equals the function applied to the history.
- Deleting or editing a call attempt is not possible from the API.
