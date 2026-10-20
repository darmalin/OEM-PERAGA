# 08 Registration, QR, Email

Spec §7. Open decisions D1, D2.

## Registration
- Channels: Website (public API), Admin manual, Telemarketing, API, Excel import.
- QR issued right after successful registration; does not wait for telemarketing.
- `visitor_registrations`: `visitor_lead_id`, `edition_id`, `channel`, `status`, `registered_at`, `idempotency_key`. Unique `(edition_id, visitor_lead_id)` for an active registration.
- `POST /visitor-registrations` requires an `Idempotency-Key` header; same key + same body returns the original result.

## QR credential
- `qr_credentials`: `registration_id`, `token_hash`, `status` (`ACTIVE`, `REVOKED`), `issued_at`, `revoked_at`.
- Token: 32 random bytes, URL-safe base64. Only the hash is stored. QR encodes the token only, never PII.
- Resend does not create a new credential. Rotate = revoke old + issue new, audited.
- Token never written to logs or audit.

Since only the hash is stored, the email job must receive the raw token at issue time (in the outbox payload, encrypted at rest or kept only until sent), or resend must rotate. Decide during M4 design; default: store the token encrypted with an app key so resend works without rotation.

## Email
- `email_templates` (versioned), `email_jobs`, `email_logs`: recipient, template + version, registration, queued_at, sent_at, provider message ID, delivery status, safe error summary.
- Sent by the worker via the outbox. Never inside the registration request.
- Retry with backoff; retry never creates a second registration.
- Resend button (needs `registration.resend_qr`).

## Public website registration
- Rate limit per IP, honeypot field + optional captcha, same duplicate rules.
- Duplicate on public form returns a neutral message (no confirmation that an email exists).

## Tasks
- [ ] Tables, outbox table `outbox_events`, dispatcher task.
- [ ] Registration service, idempotency store, QR issue/revoke.
- [ ] Email template rendering (Jinja2), QR image via `segno`, attachment or inline.
- [ ] Registration tab on the lead form: status, QR status, email log, Resend QR, Revoke QR.
- [ ] Public registration endpoint + rate limit.

## Acceptance criteria
- Same `Idempotency-Key` twice creates one registration and one email.
- QR payload contains no name, email, or phone.
- Killing the worker mid-send and restarting does not create duplicates.
