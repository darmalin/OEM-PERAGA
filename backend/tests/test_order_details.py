"""Question sets of the order forms (Phase 5 of docs/EXHIBITOR_ORDER_FORMS.md)."""

import io
from typing import Any

import pytest
from openpyxl import load_workbook

from app.core.errors import ValidationFailed
from app.modules.orders import details
from app.modules.orders.rules import DetailsType
from tests.factories import RoleGrant, actor, make_edition
from tests.test_order_forms import URL, add_form
from tests.test_order_portal import Setup, setup

ORDERS = "/api/v1/exhibitor-orders"
OPTIONS = {
    "PRODUCT_CATEGORY": {"Fabrics", "Yarns"},
    "STAND_SERVICE": {"Standard booth", "Raw space"},
    "OFFICIAL_CONTRACTOR": {"PT Example Contractor"},
    "OFFICIAL_FORWARDER": {"PT Example Logistics"},
    "SEMINAR_DATE": {"15 April 2027"},
}

COMPLETE: dict[DetailsType, dict[str, Any]] = {
    DetailsType.DIRECTORY_LISTING: {
        "agent_or_principal": "PRINCIPAL",
        "listed_as": "MANUFACTURER",
        "brief_introduction": "We weave cotton fabrics.",
        "product_categories": ["Fabrics"],
        "agent_principal_listings": [{"company": "Example Mills", "country": "Indonesia"}],
    },
    DetailsType.ADVERTISING: {},
    DetailsType.SOCIAL_MEDIA: {
        "product_category": "Yarns",
        "instagram": "https://instagram.com/example",
    },
    DetailsType.STAND_SERVICE: {
        "service": "Raw space",
        "contractor": "OWN",
        "own_contractor": {
            "name": "PT Builder",
            "pic": "Budi",
            "mobile": "0812",
            "email": "pic@example.test",
        },
    },
    DetailsType.EXHIBIT_DETAILS: {
        "items": [{"quantity": 1, "description": "Loom", "weight_kg": 1200}],
        "sale_and_operation": "SALE_OPERATED",
    },
    DetailsType.FREIGHT: {"uses_official": True, "official_forwarder": "PT Example Logistics"},
    DetailsType.BADGES_VISA: {"company_type": "LOCAL", "badge_count": 3},
    DetailsType.SEMINAR: {
        "topic": "Recycled yarns",
        "date": "15 April 2027",
        "speakers": [{"name": "Siti"}],
    },
    DetailsType.PARKING: {"plates": ["B 1234 XYZ"]},
}


@pytest.mark.parametrize("kind", list(DetailsType))
def test_complete_answers_pass(kind: DetailsType) -> None:
    answers = details.parse(kind, COMPLETE[kind], OPTIONS)
    assert details.missing(kind, answers) == {}


@pytest.mark.parametrize("kind", [k for k in DetailsType if k != DetailsType.ADVERTISING])
def test_empty_answers_are_a_valid_draft_but_not_complete(kind: DetailsType) -> None:
    assert details.parse(kind, {}, OPTIONS) == {}
    assert details.missing(kind, {}) != {}


@pytest.mark.parametrize(
    ("kind", "raw", "field"),
    [
        (
            DetailsType.DIRECTORY_LISTING,
            {"product_categories": ["Shoes"]},
            "details.product_categories.0",
        ),
        (DetailsType.DIRECTORY_LISTING, {"listed_as": "RETAILER"}, "details.listed_as"),
        (DetailsType.SOCIAL_MEDIA, {"video_link": "not a link"}, "details.video_link"),
        (
            DetailsType.STAND_SERVICE,
            {"official_contractor": "Someone else"},
            "details.official_contractor",
        ),
        (
            DetailsType.STAND_SERVICE,
            {"own_contractor": {"email": "nope"}},
            "details.own_contractor.email",
        ),
        (
            DetailsType.EXHIBIT_DETAILS,
            {"items": [{"quantity": 0, "description": "x"}]},
            "details.items.0.quantity",
        ),
        (DetailsType.SEMINAR, {"speakers": [{"name": "A"}] * 4}, "details.speakers"),
        (DetailsType.SEMINAR, {"date": "1 May 2027"}, "details.date"),
        (DetailsType.PARKING, {"plates": ["B 1234 XYZ ABCDEFG"]}, "details.plates.0"),
        (DetailsType.PARKING, {"cars": 2}, "details.cars"),
    ],
)
def test_bad_answers(kind: DetailsType, raw: dict[str, Any], field: str) -> None:
    with pytest.raises(ValidationFailed) as e:
        details.parse(kind, raw, OPTIONS)
    assert field in e.value.fields, e.value.fields


def test_conditional_requirements() -> None:
    stand = details.parse(
        DetailsType.STAND_SERVICE, {"service": "Raw space", "contractor": "OFFICIAL"}, OPTIONS
    )
    assert details.missing(DetailsType.STAND_SERVICE, stand) == {
        "details.official_contractor": "Required."
    }
    freight = details.parse(DetailsType.FREIGHT, {"uses_official": False}, OPTIONS)
    assert set(details.missing(DetailsType.FREIGHT, freight)) == {
        f"details.non_official.{f}"
        for f in ("company", "country", "phone", "email", "authorized_person")
    }
    badges = {**COMPLETE[DetailsType.BADGES_VISA], "vip_needed": True}
    assert "details.vip_badges" in details.missing(DetailsType.BADGES_VISA, badges)


def test_badges_by_company_type() -> None:
    """Indonesian companies give a count; overseas companies list each holder in full."""
    kind = DetailsType.BADGES_VISA
    holder = {"full_name": "John Lee", "designation": "Sales Manager", "company": "Lee Textiles"}
    local = details.parse(kind, {"company_type": "LOCAL", "badges": [holder]}, OPTIONS)
    assert local == {"company_type": "LOCAL"}  # names are not asked of a local company
    assert details.missing(kind, local) == {"details.badge_count": "How many badges do you need?"}
    with pytest.raises(ValidationFailed) as e:
        details.parse(kind, {"company_type": "LOCAL", "badge_count": 0}, OPTIONS)
    assert "details.badge_count" in e.value.fields

    overseas = details.parse(
        kind,
        {"company_type": "OVERSEAS", "badge_count": 4, "badges": [{"full_name": "John Lee"}]},
        OPTIONS,
    )
    assert "badge_count" not in overseas
    assert details.missing(kind, overseas) == {
        "details.badges.0.company": "Required.",
        "details.badges.0.designation": "Required.",
    }
    full = details.parse(kind, {"company_type": "OVERSEAS", "badges": [holder]}, OPTIONS)
    assert details.missing(kind, full) == {}


def test_visa_applicants() -> None:
    kind = DetailsType.BADGES_VISA
    base = {"company_type": "LOCAL", "badge_count": 2, "needs_visa_letter": True}
    answers = details.parse(kind, base, OPTIONS)
    assert details.missing(kind, answers) == {
        "details.visa_applicants": "Add the people who need the letter."
    }
    answers = details.parse(kind, {**base, "visa_applicants": [{"full_name": "Wei"}]}, OPTIONS)
    assert set(details.missing(kind, answers)) == {
        f"details.visa_applicants.0.{f}"
        for f in ("nationality", "passport_number", "passport_expiry", "designation")
    }
    with pytest.raises(ValidationFailed) as e:
        details.parse(
            kind,
            {**base, "visa_applicants": [{"full_name": "Wei", "passport_expiry": "12/2030"}]},
            OPTIONS,
        )
    assert "details.visa_applicants.0.passport_expiry" in e.value.fields
    # No letter, no applicants kept.
    no = details.parse(
        kind,
        {**base, "needs_visa_letter": False, "visa_applicants": [{"full_name": "Wei"}]},
        OPTIONS,
    )
    assert "visa_applicants" not in no


def test_answers_keep_text_and_drop_blanks() -> None:
    answers = details.parse(DetailsType.PARKING, {"plates": [" B 1 XY "]}, OPTIONS)
    assert answers == {"plates": ["B 1 XY"]}
    assert details.parse(None, {}, OPTIONS) == {}
    with pytest.raises(ValidationFailed):
        details.parse(None, {"plates": ["x"]}, OPTIONS)
    assert details.summary(DetailsType.PARKING, answers) == "plates: B 1 XY"


# --- API ---------------------------------------------------------------------------------


async def question_form(s: Setup, code: str, details_type: str, **kw: Any) -> dict[str, Any]:
    r = await add_form(
        s.admin, s.edition, code, title=f"Form {code}", details_type=details_type, **kw
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


async def set_options(s: Setup, form: dict[str, Any], kind: str, values: list[str]) -> Any:
    return await s.admin.put(f"{URL}/{form['id']}/options", json={"kind": kind, "values": values})


async def publish(s: Setup, form: dict[str, Any]) -> None:
    current = (await s.admin.get(f"{URL}/{form['id']}")).json()
    r = await s.admin.patch(
        f"{URL}/{form['id']}", json={"is_published": True, "version": current["version"]}
    )
    assert r.status_code == 200, r.text


async def test_options_api() -> None:
    s = await setup()
    form = await question_form(s, "03", "stand_service")
    r = await set_options(
        s, form, "STAND_SERVICE", [" Standard booth ", "Raw space", "Standard booth"]
    )
    assert r.status_code == 200, r.text
    assert r.json()["options"] == {"STAND_SERVICE": ["Standard booth", "Raw space"]}
    r = await set_options(s, form, "OFFICIAL_CONTRACTOR", ["PT Example Contractor"])
    assert set(r.json()["options"]) == {"STAND_SERVICE", "OFFICIAL_CONTRACTOR"}
    r = await set_options(s, form, "SEMINAR_DATE", ["15 April 2027"])
    assert r.status_code == 422  # not a choice this form's questions use
    r = await set_options(s, form, "STAND_SERVICE", [])
    assert r.json()["options"] == {"OFFICIAL_CONTRACTOR": ["PT Example Contractor"]}
    assert (await s.admin.get(f"{URL}/{form['id']}/options")).json() == r.json()

    # Read-only for other staff; copied with the form to another edition.
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", s.edition.id))
    assert (
        await agent.put(f"{URL}/{form['id']}/options", json={"kind": "STAND_SERVICE", "values": []})
    ).status_code == 403
    target = await make_edition()
    _, both = await actor(
        RoleGrant("EXHIBITION_ADMIN", "EDITION", s.edition.id),
        RoleGrant("EXHIBITION_ADMIN", "EDITION", target.id),
    )
    r = await both.post(
        f"{URL}/copy", json={"from_edition_id": str(s.edition.id), "to_edition_id": str(target.id)}
    )
    assert r.status_code == 200, r.text
    copied = next(
        f
        for f in (await both.get(URL, params={"edition_id": str(target.id)})).json()["items"]
        if f["code"] == "03"
    )
    assert (await both.get(f"{URL}/{copied['id']}/options")).json() == {
        "options": {"OFFICIAL_CONTRACTOR": ["PT Example Contractor"]}
    }


async def test_answer_and_submit_a_question_form() -> None:
    s = await setup()
    form = await question_form(s, "10", "seminar")
    await set_options(s, form, "SEMINAR_DATE", ["15 April 2027", "16 April 2027"])
    await publish(s, form)

    detail = await s.detail("10")
    assert detail["options"] == {"SEMINAR_DATE": ["15 April 2027", "16 April 2027"]}
    assert detail["details_type"] == "seminar"
    order = await s.draft("10")
    r = await s.save(order, details={"topic": "Recycled yarns", "date": "1 May 2027"})
    assert r.status_code == 422
    assert "details.date" in r.json()["error"]["fields"]
    r = await s.save(order, lines=[s.line("E-001", 1)], details={})
    assert r.status_code == 422  # no catalog on this form

    order = (
        await s.save(order, details={"topic": " Recycled yarns ", "date": "15 April 2027"})
    ).json()
    assert order["details"] == {"topic": "Recycled yarns", "date": "15 April 2027"}
    r = await s.submit(order)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "DETAILS_INCOMPLETE"
    assert r.json()["error"]["fields"] == {"details.speakers": "Add at least one speaker."}

    speakers = [
        {"name": "Siti Rahma", "company": "Example Mills", "title_of_speech": "Yarn of tomorrow"}
    ]
    order = (await s.save(order, details={**order["details"], "speakers": speakers})).json()
    sent = (await s.submit(order)).json()
    assert (sent["status"], sent["total"]) == ("SUBMITTED", "0.00")

    # Staff see the answers; a free order needs no signed contract.
    staff = (await s.admin.get(f"{ORDERS}/{sent['id']}")).json()
    assert staff["details_type"] == "seminar"
    assert staff["details"]["speakers"][0]["name"] == "Siti Rahma"
    r = await s.admin.post(
        f"{ORDERS}/{sent['id']}/review", json={"decision": "APPROVED", "version": staff["version"]}
    )
    assert r.status_code == 200, r.text

    # Later edits to the choices do not change the sent answer.
    await set_options(s, form, "SEMINAR_DATE", ["20 April 2027"])
    assert (await s.admin.get(f"{ORDERS}/{sent['id']}")).json()["details"][
        "date"
    ] == "15 April 2027"

    r = await s.admin.get(
        f"{ORDERS}/export", params={"edition_id": str(s.edition.id), "form_id": form["id"]}
    )
    ws = load_workbook(io.BytesIO(r.content)).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0][-1] == "Answers"
    assert "topic: Recycled yarns" in rows[1][-1]


async def test_catalog_form_with_questions() -> None:
    """Form 12: parking passes from the catalog plus the plate numbers."""
    s = await setup()
    current = (await s.admin.get(f"{URL}/{s.form['id']}")).json()
    r = await s.admin.patch(
        f"{URL}/{s.form['id']}", json={"details_type": "parking", "version": current["version"]}
    )
    assert r.status_code == 200, r.text
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 2)])).json()
    r = await s.submit(order)
    assert r.json()["error"]["code"] == "DETAILS_INCOMPLETE"
    order = (
        await s.save(order, lines=[s.line("E-001", 2)], details={"plates": ["B 1 AB", "B 2 CD"]})
    ).json()
    assert (await s.submit(order)).json()["status"] == "SUBMITTED"


PDF = b"%PDF-1.7\n%%EOF\n"
APPLICANT = {
    "full_name": "Wei Zhang",
    "nationality": "China",
    "passport_number": "E12345678",
    "passport_expiry": "2030-05-01",
    "designation": "Engineer",
}


async def test_visa_letter_needs_a_passport_copy_per_person(storage: Any) -> None:
    s = await setup()
    form = await question_form(s, "09", "badges_visa")
    await publish(s, form)
    assert "PASSPORT" in (await s.detail("09"))["attachment_purposes"]
    order = await s.draft("09")
    answers = {"company_type": "LOCAL", "badge_count": 2, "needs_visa_letter": True}
    two = [APPLICANT, {**APPLICANT, "full_name": "Li Na", "passport_number": "E7654321"}]
    order = (await s.save(order, details={**answers, "visa_applicants": two})).json()
    r = await s.submit(order)
    assert r.json()["error"]["fields"] == {
        "file": "Attach a passport copy for each person: 0 of 2 attached."
    }

    files_url = s.url(f"/orders/{order['id']}/files")
    for n in (1, 2):
        r = await s.portal.post(
            files_url,
            data={"purpose": "PASSPORT", "version": str(order["version"])},
            files={"file": (f"passport-{n}.pdf", PDF, "application/pdf")},
        )
        assert r.status_code == 200, r.text
        order = r.json()
    r = await s.submit(order)
    assert r.status_code == 200, r.text

    # Another form does not take passports.
    other = await s.draft()
    r = await s.portal.post(
        s.url(f"/orders/{other['id']}/files"),
        data={"purpose": "PASSPORT", "version": str(other["version"])},
        files={"file": ("passport.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 422
