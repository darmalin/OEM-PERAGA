# 08 Registration, QR, Email

Spec §7. Open decisions D1, D2.

## Registration
- Owner decision 2026-10-22: every lead is registered when it is created (manual, Excel import, API, website), so it can enter the gate whether or not telemarketing worked it. The channel follows the lead source. No QR email is sent for these (campaign link forms included); staff send it with Resend QR Email.
- Leads created before that decision: `python -m app.cli register-backlog` registers them (no email), skipping archived editions.
- Channels: Campaign link (public form, FEATURES/12), Admin manual, Telemarketing, API, Excel import. Website is kept only for older rows.
- QR issued right after successful registration; does not wait for telemarketing.
- `visitor_registrations`: `visitor_lead_id`, `edition_id`, `channel`, `status`, `registered_at`, `idempotency_key`. Unique `(edition_id, visitor_lead_id)` for an active registration.
- `POST /visitor-registrations` requires an `Idempotency-Key` header; same key + same body returns the original result.

## QR credential
- `qr_credentials`: `registration_id`, `token_hash`, `status` (`ACTIVE`, `REVOKED`), `issued_at`, `revoked_at`.
- Token: 32 random bytes, URL-safe base64. Only the hash is stored. QR encodes the token only, never PII.
- Resend does not create a new credential. Rotate = revoke old + issue new, audited.
- Token never written to logs or audit.

Since only the hash is stored, the email job must receive the raw token at issue time (in the outbox payload, encrypted at rest or kept only until sent), or resend must rotate. Decide during M4 design; default: store the token encrypted with an app key so resend works without rotation.

## Email accounts and the email log (2026-10-23)

- **Email Accounts** (System > Email Accounts, permission `email_account.manage`, Super Admin only): SMTP accounts with name, From, Reply-To, host, port, security (None, STARTTLS, SSL), username, and password. The password is Fernet-encrypted with `EMS_APP_ENCRYPTION_KEY` and never returned by the API. One account is the **Default**; the first one created becomes it, and the default cannot be turned off.
- **Which account sends** (decided at send time, recorded on the email): an edition's QR emails use the edition's Email Account (Edition form, edition admins pick from active accounts); else the default; with no account configured, the `.env` SMTP settings. System email (password reset, follow-up reminders; OTP later) always uses the default.
- **Send Test Email** queues a test message to the account's own address; the worker records Passed/Failed and the SMTP reply on the account. Rate limited to 10 per user per hour.
- **Email Log** (System > Email Log, permission `email_log.read`): every email (QR, password reset, follow-up reminder, test) with recipient, subject, account, From, status, attempts, safe error summary, and the attempt trail. Edition admins see their editions' emails; system emails (no edition) need `email_account.manage`.
- Not built: scheduled send ("send after", as in Frappe's Email Queue). Nothing needs it yet; follow-up reminders are timed by Celery Beat.

## Email
- `email_templates` (versioned), `email_jobs`, `email_logs`: recipient, template + version, registration, queued_at, sent_at, provider message ID, delivery status, safe error summary.
- Sent by the worker via the outbox. Never inside the registration request.
- Retry with backoff; retry never creates a second registration.
- Resend button (needs `registration.resend_qr`).

## Public registration
Replaced by campaign links (FEATURES/12, 2026-10-26): the website endpoint by edition code is removed.

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
