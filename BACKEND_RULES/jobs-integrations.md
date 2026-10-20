# Background Jobs and Integrations

## Celery setup
- Broker and result backend: Redis. Serializer: JSON only (never pickle).
- `task_acks_late=True`, `worker_prefetch_multiplier=1` for long tasks, `task_reject_on_worker_lost=True`.
- Queues: `default`, `email`, `import`, `export`, `reports`. Heavy queues get their own worker process in production.
- `beat` runs as exactly one container.
- Task arguments are IDs, never ORM objects or PII blobs. The task loads data itself.

## Task rules
- Every task is idempotent: running it twice has the same effect as once. Use a natural key (`email_job.id`, `followup:{id}:{due_at}`) and check state before acting.
- Retries: `autoretry_for` transient errors (SMTP timeouts, S3 5xx) with exponential backoff + jitter and a max retry count. Permanent errors mark the job `FAILED` with a safe error summary.
- Tasks log start, end, and outcome with `job_id` and `request_id` (propagated from the API).
- A task never sends email or calls an external service inside an open DB transaction that may roll back.

## Transactional outbox
- Services that need a side effect (send QR email, send reminder) insert a row in `outbox_events` in the same transaction as the business change.
- A dispatcher task (Beat every few seconds, plus a direct enqueue after commit) reads unprocessed rows with `FOR UPDATE SKIP LOCKED`, enqueues the real task, and marks the row dispatched.
- This guarantees: no email for a rolled-back registration, and no lost email when the API crashes after commit.

## Email
- `EmailSender` protocol with `SmtpSender` and provider implementations; chosen by config. Dev uses Mailpit.
- Templates: Jinja2, versioned in `email_templates`; the version used is stored on `email_jobs`.
- Every send creates/updates `email_jobs` + `email_logs` (recipient, template version, related registration, queued/sent time, provider message ID, status, safe error).
- Resend reuses the existing QR credential.

## File storage
- S3 API via `boto3`; MinIO in dev. Buckets: `imports`, `exports`. Object keys random (`uuid7`).
- Downloads via presigned URLs with short expiry, generated only after a permission check.

## Excel
- Import: `openpyxl.load_workbook(read_only=True, data_only=True)`, stream rows, process in batches (e.g. 500) with a savepoint per row so a single failure is reported, not fatal.
- Export: `openpyxl` write-only mode. Respect `in_export` on custom fields. Same scope filter as the list endpoint.
- Formula injection: prefix cell values starting with `=`, `+`, `-`, `@` with `'` on export.

## Scheduling
- Follow-up reminders (once D4 is decided), outbox dispatch, export cleanup, expired idempotency keys cleanup, scanner cache expiry checks.
