"""QR email templates. Admin-editable, so rendered in a Jinja2 sandbox with strict undefined."""

from dataclasses import dataclass
from datetime import date
from typing import Any

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from app.core.errors import ValidationFailed

QR_IMAGE_CID = "qr-code"

DEFAULT_SUBJECT = "Your entry QR code for {{ edition_name }}"

DEFAULT_TEXT = """Hello {{ first_name }},

You are registered for {{ edition_name }}, {{ start_date }} to {{ end_date }}\
{% if city %} in {{ city }}{% endif %}.

Registration ID: {{ registration_code }}

Show the attached QR code at the entrance gate. The code is personal; do not share it.
"""

DEFAULT_HTML = """<p>Hello {{ first_name }},</p>
<p>You are registered for <strong>{{ edition_name }}</strong>, {{ start_date }} to {{ end_date }}\
{% if city %} in {{ city }}{% endif %}.</p>
<p>Registration ID: <strong>{{ registration_code }}</strong></p>
<p><img src="cid:{{ qr_cid }}" alt="Entry QR code" width="240" height="240"></p>
<p>Show this QR code at the entrance gate. The code is personal; do not share it.</p>
"""

# Variables a template may use. Rendering with StrictUndefined rejects anything else.
SAMPLE_CONTEXT: dict[str, Any] = {
    "first_name": "Visitor",
    "registration_code": "EX2027000001",
    "edition_name": "Exhibition 2027",
    "edition_code": "EX2027",
    "start_date": "10-03-2027",
    "end_date": "12-03-2027",
    "city": "Jakarta",
    "qr_cid": QR_IMAGE_CID,
}

_text_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)
_html_env = SandboxedEnvironment(undefined=StrictUndefined, autoescape=True)


@dataclass(frozen=True)
class Rendered:
    subject: str
    text: str
    html: str


def _fmt(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def context(
    *,
    first_name: str,
    registration_code: str,
    edition_name: str,
    edition_code: str,
    start_date: date,
    end_date: date,
    city: str | None,
) -> dict[str, Any]:
    return {
        "first_name": first_name,
        "registration_code": registration_code,
        "edition_name": edition_name,
        "edition_code": edition_code,
        "start_date": _fmt(start_date),
        "end_date": _fmt(end_date),
        "city": city or "",
        "qr_cid": QR_IMAGE_CID,
    }


def render(subject: str, text: str, html: str, ctx: dict[str, Any]) -> Rendered:
    return Rendered(
        subject=_text_env.from_string(subject).render(ctx).strip().replace("\n", " "),
        text=_text_env.from_string(text).render(ctx),
        html=_html_env.from_string(html).render(ctx),
    )


def validate(subject: str, text: str, html: str) -> None:
    """Reject syntax errors and unknown variables before a template version is saved."""
    errors: dict[str, str] = {}
    for name, source, env in (
        ("subject", subject, _text_env),
        ("body_text", text, _text_env),
        ("body_html", html, _html_env),
    ):
        try:
            env.from_string(source).render(SAMPLE_CONTEXT)
        except TemplateError as e:
            errors[name] = str(e.message or e)[:200]
    if "{{ qr_cid }}" not in html.replace("{{qr_cid}}", "{{ qr_cid }}"):
        errors.setdefault("body_html", 'Must include <img src="cid:{{ qr_cid }}"> for the QR code.')
    if errors:
        raise ValidationFailed("Template is not valid.", fields=errors)
