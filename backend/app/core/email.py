import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    mime_type: str
    content_id: str | None = None


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    html: str
    text: str
    attachments: list[Attachment] = field(default_factory=list)
    # Display name for the configured sender address (edition email settings).
    from_name: str | None = None
    reply_to: str | None = None


@dataclass(frozen=True)
class SmtpAccount:
    """One sending account (mail module "Email Accounts"); None means the .env settings."""

    host: str
    port: int
    security: str  # NONE, STARTTLS, SSL
    username: str | None
    password: str
    from_address: str
    from_name: str | None = None
    reply_to: str | None = None


def env_account() -> SmtpAccount:
    """The .env SMTP settings, used while no account is configured in the app."""
    s = get_settings()
    name, address = parseaddr(s.email_from)
    return SmtpAccount(
        host=s.smtp_host,
        port=s.smtp_port,
        security="STARTTLS" if s.smtp_use_tls else "NONE",
        username=s.smtp_username,
        password=s.smtp_password.get_secret_value(),
        from_address=address,
        from_name=name or None,
    )


class EmailSender(Protocol):
    def send(self, email: OutgoingEmail, account: SmtpAccount | None = None) -> str:
        """Send through `account` (default: .env settings) and return the provider message ID."""
        ...


class TransientEmailError(Exception):
    """Retriable failure (timeouts, 4xx SMTP)."""


class PermanentEmailError(Exception):
    """Final failure (5xx SMTP: authentication, recipient refused). Message is safe to show."""


class SmtpSender:
    def send(self, email: OutgoingEmail, account: SmtpAccount | None = None) -> str:
        acc = account or env_account()
        msg = EmailMessage()
        # The edition's sender name wins over the account's own display name.
        msg["From"] = formataddr((email.from_name or acc.from_name or "", acc.from_address))
        msg["To"] = email.to
        reply_to = email.reply_to or acc.reply_to
        if reply_to:
            msg["Reply-To"] = reply_to
        msg["Subject"] = email.subject
        domain = acc.from_address.rpartition("@")[2] or "ems.local"
        message_id = make_msgid(domain=domain)
        msg["Message-ID"] = message_id
        msg.set_content(email.text)
        msg.add_alternative(email.html, subtype="html")
        html_part = msg.get_body(preferencelist=("html",))
        assert html_part is not None  # noqa: S101 - added just above
        for att in email.attachments:
            maintype, subtype = att.mime_type.split("/", 1)
            if att.content_id:
                html_part.add_related(
                    att.content, maintype=maintype, subtype=subtype, cid=f"<{att.content_id}>"
                )
            else:
                msg.add_attachment(
                    att.content, maintype=maintype, subtype=subtype, filename=att.filename
                )
        try:
            smtp_cls = smtplib.SMTP_SSL if acc.security == "SSL" else smtplib.SMTP
            with smtp_cls(acc.host, acc.port, timeout=30) as smtp:
                if acc.security == "STARTTLS":
                    smtp.starttls()
                if acc.username:
                    smtp.login(acc.username, acc.password)
                smtp.send_message(msg)
        except (
            smtplib.SMTPServerDisconnected,
            smtplib.SMTPConnectError,
            TimeoutError,
        ) as e:
            raise TransientEmailError(type(e).__name__) from e
        except smtplib.SMTPResponseException as e:
            # 4xx is temporary (greylisting, rate limit); 5xx is final (auth, bad recipient).
            detail = f"{e.smtp_code} {safe_smtp_text(e.smtp_error)}"
            if 400 <= e.smtp_code < 500:
                raise TransientEmailError(detail) from e
            raise PermanentEmailError(detail) from e
        except smtplib.SMTPRecipientsRefused as e:
            codes = sorted({code for code, _ in e.recipients.values()})
            raise PermanentEmailError(f"Recipient refused ({', '.join(map(str, codes))})") from e
        except OSError as e:
            raise TransientEmailError(type(e).__name__) from e
        return message_id


def safe_smtp_text(raw: bytes | str) -> str:
    """First line of an SMTP reply, short: shown in the email log, never a traceback."""
    text = raw.decode(errors="replace") if isinstance(raw, bytes) else raw
    return text.splitlines()[0][:200] if text else ""


class MemorySender:
    """Captures emails in tests."""

    def __init__(self) -> None:
        self.outbox: list[OutgoingEmail] = []
        self.accounts: list[SmtpAccount | None] = []

    def send(self, email: OutgoingEmail, account: SmtpAccount | None = None) -> str:
        self.outbox.append(email)
        self.accounts.append(account)
        return f"<memory-{len(self.outbox)}@ems.test>"


_override: list[EmailSender] = []


def set_email_sender(sender: EmailSender | None) -> None:
    _override.clear()
    if sender is not None:
        _override.append(sender)


def get_email_sender() -> EmailSender:
    if _override:
        return _override[0]
    if get_settings().email_backend == "memory":
        sender = MemorySender()
        _override.append(sender)
        return sender
    return SmtpSender()
