# Security, Permissions, Audit

## Authentication
- Server-side sessions stored in Redis; the cookie holds only a random session ID.
- Cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`. Rotate the session ID on login and privilege change.
- Idle timeout and absolute timeout (values in config). Logout deletes the session server-side.
- CSRF: token bound to the session, sent in `X-CSRF-Token` on every unsafe method, compared in constant time.
- Passwords: Argon2id. Minimum length 12, check against a common-password list. No password in logs, audit, or responses.
- Login and password reset are rate limited; failed logins are audited.
- Scanner devices authenticate with a device credential (hashed in DB), not with a user session, plus the gate staff's session for attribution when available.

## Authorization: permission + scope on every endpoint

```python
@router.get("/visitor-leads")
async def list_leads(
    params: LeadListParams = Depends(),
    ctx: AuthContext = Depends(require("visitor.read")),
    service: VisitorService = Depends(),
) -> Page[LeadOut]:
    return await service.list(ctx.scope_for(params.edition_id), params)
```

- `require("<permission>")` returns an `AuthContext` or raises 403. Every route has one. A test asserts that every registered route (except login, health, public registration) depends on `require`.
- `ctx.scope_for(edition_id)` resolves the user's scope for that edition (`EDITION`, `TEAM`, `OWNED`, `GATE`) or raises 404.
- Scope is applied in the repository query, not by filtering results in Python.
- `OWNED` = lead owner is the user. `TEAM` = owner is in one of the user's teams. `GATE` = gate/device assigned to the user.
- Checks use permissions, never role names (`if user.role == "SUPER_ADMIN"` fails review).
- Export, reassign, resend QR, gate override each need their own permission (spec §9).

## Audit log
- Call `audit.record(session, actor, source, entity_type, entity_id, action, before, after)` inside the same transaction as the change.
- Record only changed fields. Redact keys in the denylist: `password`, `password_hash`, `session_id`, `csrf_token`, `token`, `token_hash`, `qr_token`, `device_secret`, `smtp_password`, `api_key`.
- Audit rows are append-only (DB grants). Reading needs `audit_log.read`.

## PII handling
- Visitor email, phone, name are PII. Do not put them in URLs (use IDs), logs (mask), job names, or error messages to public clients.
- QR tokens: 32 random bytes from `secrets`. Store hash (SHA-256) for lookup; if resend needs the raw token, store it encrypted with the app key (see FEATURES/08). Never log.
- Exports: signed URL with short expiry, audited, deleted by a cleanup task.
- Retention policy pending (D9). Design tables so a purge job can be added without schema changes.

## Uploads
- Accept only `.xlsx` for import; check extension, MIME, and open with `openpyxl` in read-only mode inside the worker. Size limit in nginx and API.
- Store uploads in S3/MinIO with random object keys, never on the API container filesystem.

## HTTP hardening (nginx + app)
- HTTPS only, HSTS in production.
- Headers: `Content-Security-Policy` (no inline scripts), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy` (camera only on the scanner origin/path).
- CORS: same-origin by default. Allow only the configured website origin for the public registration endpoint.

## Secrets
- From env/secret store only. `.env.example` has names and dummy values, no real values. Rotate SMTP/S3 keys without code changes.
