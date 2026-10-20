# 07 Telemarketing: Calls, Verification, Follow-ups

Spec §6.2 to §6.5. Open decisions D3, D4, D7.

## Telemarketing status (derived, never typed in)

| Status | Rule |
|---|---|
| `NEW` | No attempts |
| `ANSWER` | Attempt 1, answered |
| `NO_ANSWER` | Attempt 1, not answered |
| `RECONTACTED` | Attempt 2+, last answered |
| `RETRY_NO_ANSWER` | Attempt 2+, last not answered |

Computed from `visitor_call_activities` on every insert and stored on the lead as a summary. One pure function, fully unit tested.

## Call activity
`visitor_call_activities`: `id`, `visitor_lead_id`, `agent_id`, `attempt_number`, `call_result`, `called_at`, `duration_seconds`, `notes`, `next_followup_at`, `created_at`. No VoIP; agents log manually. `attempt_number` assigned under row lock on the lead.

Call results: `ANSWER`, `NO_ANSWER` by default; extra values only through config (D7).

## Verification
- Fields: Valid Lead / Invalid (mutually exclusive, DB check constraint), Attend (5 fixed values), B2B Matching, Type of Buyers (B-Side / C-Side).
- Partial save allowed.
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
