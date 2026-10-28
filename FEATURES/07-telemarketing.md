# 07 Telemarketing: Calls, Verification, Follow-ups

Spec §6.2 to §6.5. Open decisions D3, D4, D7.

## Telemarketing status (derived, never typed in)

Owner decisions 2026-10-22 (second round, replaces the first table of the same day). Every call is
accepted; some leave the status as it is.

| From | Answered call | Not answered call |
|---|---|---|
| `NEW` | `ANSWER` | `NO_ANSWER` |
| `ANSWER` | `RECONTACTED` | `RETRY_NO_ANSWER` |
| `NO_ANSWER` | `RECONTACTED` | `RETRY_NO_ANSWER` |
| `RETRY_NO_ANSWER` | `RECONTACTED` | stays `RETRY_NO_ANSWER` |
| `RECONTACTED` | stays `RECONTACTED` | stays `RECONTACTED` |

Scenarios (owner-validated):
1. Answered first: New → Answer.
2. Not answered, then answered: New → No Answer → Recontacted.
3. Two misses, then answered: New → No Answer → Retry No Answer → Recontacted.
4. Answered, then not answered: New → Answer → Retry No Answer. The missed call requires Lead Quality and clears Attend, B2B Matching, and Type of Buyers. Answered later: Recontacted.
5. Never answered: New → No Answer → Retry No Answer, and every later miss is logged while the status stays.
6. Recontacted and called again: stays Recontacted; an answered call may update the verification.

- Stored on the lead, recomputed from `visitor_call_activities` by replaying the table (`telemarketing.rules.telemarketing_status`), under the lead row lock. Migrations `0012` (first table) and `0014` (this table) recomputed every stored status; leads moved No Answer → Answer under the first table became Recontacted.
- Owner update (2026-10-28): a missed call after Answer moves to Retry No Answer. Recontacted remains terminal. Existing call records are preserved; the updated table applies when the next call is saved.
- Board: `/app/visitor-leads/board`. A card moves by drag or its + menu. Both open Log Call with the target in a modal over the board (2026-10-28); the board keeps its filters and scroll, and the status changes only when the call is saved. The menu's Log Call covers calls that keep the status. The menu labels read "current to target", e.g. Answer to Retry No Answer.

Change log: first table (2026-10-22, morning) had Answer → only Recontacted, No Answer → Answer, and Recontacted / Retry No Answer final with no further calls.

## Call activity
`visitor_call_activities`: `id`, `visitor_lead_id`, `agent_id`, `attempt_number`, `call_result`, `called_at`, `duration_seconds`, `notes`, `next_followup_at`, `created_at`. No VoIP; agents log manually. `attempt_number` assigned under row lock on the lead.

Call results: `ANSWER`, `NO_ANSWER` by default; extra values only through config (D7).

## Verification
- Fields: Lead Quality (Valid / Invalid / Undecided, stored as the two mutually exclusive flags `is_valid_lead` / `is_invalid`), Attend (5 fixed values), B2B Matching, Type of Buyers (B-Side / C-Side).
- Lead Quality says whether the phone or email reached a real visitor.
- Sent with a call as `verification` (owner decisions 2026-10-22), rules in `telemarketing.rules.call_verification_errors`:
  - Answered: Lead Quality must be Valid and Attend is required; B2B Matching and Type of Buyers optional.
  - Not answered and the lead moves (to No Answer or Retry No Answer): Lead Quality required. Attend, B2B Matching, and Type of Buyers are not accepted (422) and are cleared on the lead.
  - Not answered and the status stays (repeated retry misses or Recontacted): verification optional; the stored values are kept.
- Verification tab (`PATCH /visitor-leads/{id}/verification`): partial save between calls. While the lead is No Answer or Retry No Answer (never reached), only Lead Quality is accepted.
- `visitor_verifications` keeps history rows (one per save or call that carried verification); the lead holds the current values.
- `Hang Up Immediately` in Attend does not mean "not attending"; the call result is recorded separately.

## Follow-up
`visitor_followups`: `visitor_lead_id`, `assigned_to`, `due_at`, `status` (`OPEN`, `DONE`, `CANCELLED`), `created_from_call_id`, history of reschedules.

## Tasks
- [ ] Tables, constraints, status function + tests.
- [ ] `POST /visitor-leads/{id}/calls`, `PATCH /visitor-leads/{id}/verification`, `POST /visitor-leads/{id}/followups`, `PATCH /followups/{id}` (reschedule, done, cancel).
- [x] ~~"My Calls" queue for agents~~ removed from the menu (owner request 2026-10-28). `/app/my-calls` redirects to Visitor Leads with Lead Owner = Me (team view: the chosen agent). The `my-queue` and `team-queue` endpoints still exist.
- [ ] "Log Call" dialog on the lead form: result, notes, optional next follow-up. Verification section editable when the last result is Answer.
- [x] ~~Follow-ups list~~ removed (owner request 2026-10-28). `/app/followups` redirects to Visitor Leads; a follow-up is added and seen on the lead (Add Follow-up), on the board card, and through the Next Follow-up filter. `/app/followups/{id}` still opens one follow-up.
- [ ] Manager view (`telemarketing.view_team`): team queue, filter by agent.
- [ ] Email reminder job (Celery Beat) behind D4; idempotency key `followup:{id}:{due_at}` so a reminder is never sent twice.
- [ ] Audit everything.

## Acceptance criteria
- Two agents logging a call on the same lead at once get attempt numbers 1 and 2, not 1 and 1.
- Status always equals the function applied to the history. Exception since 2026-10-28: leads whose history is Answer then a missed call still show Answer until their next call, because the table changed without recomputing stored statuses (BACKEND_RULES/known-gaps.md B2).
- Deleting or editing a call attempt is not possible from the API.

Call form update (owner request, 2026-10-28): remove Next Follow-up from the shared call form and omit it from call submissions. Existing schedules and the separate per-lead Add Follow-up flow remain available.
