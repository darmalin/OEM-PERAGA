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


class EmailSender(Protocol):
    def send(self, email: OutgoingEmail) -> str:
        """Send and return the provider message ID."""
        ...


class TransientEmailError(Exception):
    """Retriable failure (timeouts, 4xx SMTP)."""


class SmtpSender:
    def send(self, email: OutgoingEmail) -> str:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = (
            formataddr((email.from_name, parseaddr(s.email_from)[1]))
            if email.from_name
            else s.email_from
        )
        msg["To"] = email.to
        if email.reply_to:
            msg["Reply-To"] = email.reply_to
        msg["Subject"] = email.subject
        message_id = make_msgid(domain="ems.local")
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
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
                if s.smtp_use_tls:
                    smtp.starttls()
                if s.smtp_username:
                    smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
                smtp.send_message(msg)
        except (
            smtplib.SMTPServerDisconnected,
            smtplib.SMTPConnectError,
            TimeoutError,
            OSError,
        ) as e:
            raise TransientEmailError(type(e).__name__) from e
        return message_id


class MemorySender:
    """Captures emails in tests."""

    def __init__(self) -> None:
        self.outbox: list[OutgoingEmail] = []

    def send(self, email: OutgoingEmail) -> str:
        self.outbox.append(email)
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
