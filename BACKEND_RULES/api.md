# API Rules

## Basics
- Prefix `/api/v1`. Resources plural, kebab-case: `/visitor-leads`, `/visitor-registrations`, `/gate/scans`.
- JSON fields `snake_case`, English.
- Methods: `GET` read, `POST` create or action, `PATCH` partial update, `DELETE` only where the spec allows deletion (none of the history tables).
- Actions that are not CRUD are sub-resources: `POST /visitor-leads/{id}/calls`, `POST /visitor-registrations/{id}/resend-qr`.
- Every route declares `response_model`, so OpenAPI is complete and the frontend client is generated from it.
- Edition context: event-data endpoints take `edition_id` (query param on lists, field on create). The server checks it against scope; it never trusts it blindly.

## Status codes

| Code | When |
|---|---|
| 200 / 201 | Success / created |
| 202 | Job accepted (import, export, large assignment) |
| 400 | Malformed request |
| 401 | Not logged in / session expired |
| 403 | Logged in, missing permission |
| 404 | Not found **or** outside the caller's scope (do not reveal existence) |
| 409 | Duplicate (email/phone), version conflict, idempotency key reused with different body |
| 422 | Validation failed |
| 429 | Rate limited |

## Error envelope

```json
{
  "error": {
    "code": "DUPLICATE_VISITOR",
    "message": "Email already used by IBTE2027000045 in this edition.",
    "fields": { "email": "Already used in this edition." },
    "request_id": "01JB..."
  }
}
```

- `code` is a stable `UPPER_SNAKE` string the frontend can switch on.
- `fields` maps to form fields for 409/422.
- Override FastAPI's default 422 handler to produce this shape.
- Public endpoints (website registration) must not reveal whether an email exists; they return a neutral message.

## Pagination, filtering, sorting
- Query params: `page`, `page_size` (max 500), `sort` (`-updated_at`), filters as named params (`telemarketing_status=NEW&lead_owner_id=...`).
- Response: `{ "items": [...], "total": 1284, "page": 1, "page_size": 20 }`. For very large lists, keyset pagination (`cursor`) is allowed; then `total` may be omitted.
- Filter names follow the column names. Unknown filter params return 422.

## Updates
- `PATCH` bodies are partial; only sent fields change.
- Form-edited resources require `version` in the body; mismatch returns 409 `VERSION_CONFLICT`.

## Idempotency
- Endpoints that create side effects accept `Idempotency-Key` header: registrations, resend QR, assignments, scan sync (per item via `scan_event_id`).
- Store key + request hash + response for at least 24 h. Same key + same hash returns the stored response; same key + different hash returns 409.

## Jobs
- Long operations return `202` with `{ "job_id": "...", "status": "QUEUED" }` and a `GET` status endpoint. Clients poll.

## Rate limiting and abuse
- Login, password reset, and public registration: per-IP and per-identifier limits (Redis).
- Public registration: honeypot field, optional captcha, payload size limit.

## Versioning and docs
- Breaking changes go to `/api/v2`. Additive changes stay in v1.
- OpenAPI available at `/api/v1/openapi.json` in dev and staging; disabled or protected in production.
