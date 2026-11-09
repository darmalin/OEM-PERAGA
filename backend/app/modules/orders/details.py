"""Question sets of the order forms (decision O10, Phase 5 of docs/EXHIBITOR_ORDER_FORMS.md).

Each DetailsType has one schema in code. A draft may be incomplete, so every field is optional and
only its shape and choices are checked when saving; `missing()` lists what a submit still needs.
Answers keep the chosen text, not an option id, so later edits to the choices never change a sent
order. Stored in `exhibitor_orders.details` (JSONB, the documented exception).
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.core.errors import ValidationFailed
from app.modules.orders.rules import DetailsType, OptionKind


def _text(n: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=n)


Short = Annotated[str, _text(200)]
Long = Annotated[str, _text(2000)]
Text800 = Annotated[str, _text(800)]
Text300 = Annotated[str, _text(300)]
Text100 = Annotated[str, _text(100)]
Text50 = Annotated[str, _text(50)]
Plate = Annotated[str, _text(15)]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=500, pattern=r"^https?://\S+$")
]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
Phone = Text50


class _Answers(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- 01 E-Directory Listing --------------------------------------------------------------


class AgentPrincipal(_Answers):
    company: Short
    country: Short | None = None


class DirectoryListing(_Answers):
    agent_or_principal: Literal["AGENT", "PRINCIPAL"] | None = None
    listed_as: (
        Literal["MANUFACTURER", "DISTRIBUTOR_AGENT", "LOOKING_FOR_DISTRIBUTOR", "NONE"] | None
    ) = None
    brief_introduction: Long | None = None
    product_categories: list[Short] = Field(default_factory=list, max_length=30)
    product_details: Long | None = None
    agent_principal_listings: list[AgentPrincipal] = Field(default_factory=list, max_length=20)
    looking_for_local_agent: bool | None = None


# --- 02 Advertising (the ads themselves are catalog items) -------------------------------


class Advertising(_Answers):
    logo_shape: Literal["SQUARE", "RECTANGLE"] | None = None
    image_url: Url | None = None


# --- 02a Social Media Promotion ----------------------------------------------------------


class SocialMedia(_Answers):
    product_category: Short | None = None
    product_description: Text800 | None = None
    video_link: Url | None = None
    video_title: Short | None = None
    video_description: Text800 | None = None
    facebook: Url | None = None
    x: Url | None = None
    linkedin: Url | None = None
    instagram: Url | None = None
    youtube: Url | None = None


# --- 03 Stand Service & Construction -----------------------------------------------------


class OwnContractor(_Answers):
    name: Short | None = None
    pic: Short | None = None
    address: Long | None = None
    mobile: Phone | None = None
    email: Email | None = None


class StandService(_Answers):
    service: Short | None = None
    contractor: Literal["OFFICIAL", "OWN"] | None = None
    official_contractor: Short | None = None
    own_contractor: OwnContractor | None = None


# --- 08 Exhibit Details (Machinery) ------------------------------------------------------


class ExhibitRow(_Answers):
    quantity: int = Field(gt=0, le=9999)
    description: Short
    dimension: Text100 | None = None
    weight_kg: float | None = Field(default=None, ge=0, le=1_000_000)


class ExhibitDetails(_Answers):
    items: list[ExhibitRow] = Field(default_factory=list, max_length=50)
    sale_and_operation: (
        Literal[
            "SALE_OPERATED",
            "SALE_DISPLAY_ONLY",
            "NOT_FOR_SALE_DISPLAY_ONLY",
            "NOT_FOR_SALE_OPERATED",
        ]
        | None
    ) = None
    purchased: bool | None = None


# --- 08a Freight Forwarder ---------------------------------------------------------------


class NonOfficialForwarder(_Answers):
    company: Short | None = None
    agent: Short | None = None
    address: Long | None = None
    country: Short | None = None
    city: Short | None = None
    phone: Phone | None = None
    email: Email | None = None
    authorized_person: Short | None = None
    designation: Short | None = None


class Shipment(_Answers):
    quantity: int = Field(gt=0, le=9999)
    description: Short
    length_m: float | None = Field(default=None, ge=0, le=1000)
    width_m: float | None = Field(default=None, ge=0, le=1000)
    height_m: float | None = Field(default=None, ge=0, le=1000)
    weight_kg: float | None = Field(default=None, ge=0, le=1_000_000)


class Freight(_Answers):
    uses_official: bool | None = None
    official_forwarder: Short | None = None
    non_official: NonOfficialForwarder | None = None
    shipments: list[Shipment] = Field(default_factory=list, max_length=50)


# --- 09 Exhibitor Badges & Visa ----------------------------------------------------------


class Badge(_Answers):
    full_name: Short
    gender: Literal["MALE", "FEMALE"] | None = None
    designation: Short | None = None


class VipBadge(_Answers):
    full_name: Short
    designation: Short | None = None
    company: Short | None = None


class BadgesVisa(_Answers):
    company_type: Literal["LOCAL", "OVERSEAS"] | None = None
    badges: list[Badge] = Field(default_factory=list, max_length=50)
    vip_needed: bool | None = None
    vip_badges: list[VipBadge] = Field(default_factory=list, max_length=20)
    needs_visa_letter: bool | None = None


# --- 10 Seminar --------------------------------------------------------------------------


class Speaker(_Answers):
    name: Short
    designation: Short | None = None
    company: Short | None = None
    title_of_speech: Short | None = None


class Seminar(_Answers):
    topic: Text300 | None = None
    date: Short | None = None
    time: Text50 | None = None
    speakers: list[Speaker] = Field(default_factory=list, max_length=3)


# --- 12 Parking Pass ---------------------------------------------------------------------


class Parking(_Answers):
    plates: list[Plate] = Field(default_factory=list, max_length=50)


SCHEMAS: dict[DetailsType, type[_Answers]] = {
    DetailsType.DIRECTORY_LISTING: DirectoryListing,
    DetailsType.ADVERTISING: Advertising,
    DetailsType.SOCIAL_MEDIA: SocialMedia,
    DetailsType.STAND_SERVICE: StandService,
    DetailsType.EXHIBIT_DETAILS: ExhibitDetails,
    DetailsType.FREIGHT: Freight,
    DetailsType.BADGES_VISA: BadgesVisa,
    DetailsType.SEMINAR: Seminar,
    DetailsType.PARKING: Parking,
}

Options = dict[str, set[str]]  # option kind -> allowed texts


def _choice(
    errors: dict[str, str], options: Options, kind: OptionKind, field: str, value: str | None
) -> None:
    if value is not None and value not in options.get(kind, set()):
        errors[f"details.{field}"] = "Choose one of the listed options."


def parse(details_type: str | None, raw: dict[str, Any], options: Options) -> dict[str, Any]:
    """Shape and choices of a saved draft; returns the answers to store (empty parts dropped)."""
    if details_type is None:
        if raw:
            raise ValidationFailed(fields={"details": "This form has no questions."})
        return {}
    try:
        answers = SCHEMAS[DetailsType(details_type)].model_validate(raw)
    except ValidationError as e:
        raise ValidationFailed(
            fields={
                "details." + ".".join(str(x) for x in err["loc"]): err["msg"] for err in e.errors()
            }
        ) from e
    errors: dict[str, str] = {}
    if isinstance(answers, DirectoryListing):
        for n, category in enumerate(answers.product_categories):
            _choice(
                errors, options, OptionKind.PRODUCT_CATEGORY, f"product_categories.{n}", category
            )
    elif isinstance(answers, SocialMedia):
        _choice(
            errors,
            options,
            OptionKind.PRODUCT_CATEGORY,
            "product_category",
            answers.product_category,
        )
    elif isinstance(answers, StandService):
        _choice(errors, options, OptionKind.STAND_SERVICE, "service", answers.service)
        _choice(
            errors,
            options,
            OptionKind.OFFICIAL_CONTRACTOR,
            "official_contractor",
            answers.official_contractor,
        )
    elif isinstance(answers, Freight):
        _choice(
            errors,
            options,
            OptionKind.OFFICIAL_FORWARDER,
            "official_forwarder",
            answers.official_forwarder,
        )
    elif isinstance(answers, Seminar):
        _choice(errors, options, OptionKind.SEMINAR_DATE, "date", answers.date)
    if errors:
        raise ValidationFailed(fields=errors)
    return answers.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def _need(
    errors: dict[str, str], answers: dict[str, Any], field: str, message: str = "Required."
) -> None:
    value = answers.get(field)
    if value is None or value == [] or value == {}:
        errors[f"details.{field}"] = message


def missing(details_type: str | None, answers: dict[str, Any]) -> dict[str, str]:
    """What a submit still needs, by field. Answers were already checked by `parse`."""
    if details_type is None:
        return {}
    errors: dict[str, str] = {}
    kind = DetailsType(details_type)
    if kind == DetailsType.DIRECTORY_LISTING:
        _need(errors, answers, "agent_or_principal")
        _need(errors, answers, "listed_as")
        _need(errors, answers, "brief_introduction")
        _need(errors, answers, "product_categories", "Choose at least one category.")
    elif kind == DetailsType.SOCIAL_MEDIA:
        _need(errors, answers, "product_category")
    elif kind == DetailsType.STAND_SERVICE:
        _need(errors, answers, "service")
        _need(errors, answers, "contractor")
        if answers.get("contractor") == "OFFICIAL":
            _need(errors, answers, "official_contractor")
        elif answers.get("contractor") == "OWN":
            own = answers.get("own_contractor") or {}
            for field in ("name", "pic", "mobile", "email"):
                if not own.get(field):
                    errors[f"details.own_contractor.{field}"] = "Required."
    elif kind == DetailsType.EXHIBIT_DETAILS:
        _need(errors, answers, "items", "Add at least one exhibit.")
        _need(errors, answers, "sale_and_operation")
    elif kind == DetailsType.FREIGHT:
        if "uses_official" not in answers:
            errors["details.uses_official"] = "Required."
        elif answers["uses_official"]:
            _need(errors, answers, "official_forwarder")
        else:
            agent = answers.get("non_official") or {}
            for field in ("company", "country", "phone", "email", "authorized_person"):
                if not agent.get(field):
                    errors[f"details.non_official.{field}"] = "Required."
    elif kind == DetailsType.BADGES_VISA:
        _need(errors, answers, "company_type")
        _need(errors, answers, "badges", "Add at least one badge holder.")
        if answers.get("vip_needed"):
            _need(errors, answers, "vip_badges", "Add the VIP guests or untick VIP badges.")
    elif kind == DetailsType.SEMINAR:
        _need(errors, answers, "topic")
        _need(errors, answers, "date")
        _need(errors, answers, "speakers", "Add at least one speaker.")
    elif kind == DetailsType.PARKING:
        _need(errors, answers, "plates", "Add at least one plate number.")
    return errors


def summary(details_type: str | None, answers: dict[str, Any]) -> str:
    """One readable line of the answers, for the export."""
    parts: list[str] = []
    for key, value in answers.items():
        label = key.replace("_", " ")
        if isinstance(value, list):
            rows = [
                ", ".join(str(v) for v in row.values()) if isinstance(row, dict) else str(row)
                for row in value
            ]
            parts.append(f"{label}: " + "; ".join(rows))
        elif isinstance(value, dict):
            parts.append(
                f"{label}: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in value.items())
            )
        elif isinstance(value, bool):
            parts.append(f"{label}: {'yes' if value else 'no'}")
        else:
            parts.append(f"{label}: {value}")
    return " | ".join(parts) if details_type else ""
