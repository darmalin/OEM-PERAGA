"""Quotations before a lead becomes an exhibitor (Phase 2 of docs/EXHIBITOR_QUOTATIONS.md).
The amounts are those of the sales team's Excel sheets."""

import base64
from decimal import Decimal
from typing import Any

from httpx import AsyncClient

from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition
from app.modules.quotations.rules import Term, compute
from tests.factories import RoleGrant, actor, make_edition
from tests.test_booths import LEADS, add_booth, opportunity
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, create, move, sales_role

SETTINGS = {
    "code": "IIT",
    "start_number": 113,
    "letter_name": "INATEX 2027 (The 23rd Indonesia International Textile Sourcing Expo)",
    "event_text": "14-17 April 2027 at JIEXPO Kemayoran",
    "rates": [
        {"currency": "IDR", "stand_type": "RAW", "rate": "5050000"},
        {"currency": "IDR", "stand_type": "SHELL", "rate": "5100000"},
        {"currency": "USD", "stand_type": "RAW", "rate": "365"},
        {"currency": "USD", "stand_type": "SHELL", "rate": "395"},
    ],
    "terms": [
        {"label": "Booking Fee", "percent": "30", "due_on": "2026-07-24"},
        {"label": "First Payment", "percent": "50", "due_on": "2026-11-01"},
        {"label": "Last Payment", "percent": "20", "due_on": "2027-02-01"},
    ],
    "signer_name": "Sephy Yusianty",
    "signer_title": "Sales & Marketing",
}
# PT. ASIA PACIFIC RAYON, sheet INA IDR of the raw space file.
APR = {
    "stand_type": "RAW",
    "width_m": "15.5",
    "length_m": "18",
    "complimentary_sqm": "21",
    "discount_percent": "25",
    "issued_on": "2026-07-17",
    "attention": "Ms. Novy",
    "recipient_address": "Jl. Teluk Betung No. 31 Kebon Melati, Tanah Abang\nJakarta Pusat 10230",
}


def url(edition: Edition) -> str:
    return f"/api/v1/editions/{edition.id}/quotation-settings"


async def setup(**settings: Any) -> tuple[Edition, AsyncClient, dict[str, Any]]:
    edition = await make_edition()
    admin = await admin_for(edition)
    r = await admin.put(url(edition), json=SETTINGS | settings)
    assert r.status_code == 200, r.text
    lead = (await create(admin, edition, email="apr@example.test")).json()
    return edition, admin, lead


async def quote(client: AsyncClient, lead: dict[str, Any], **body: Any) -> Any:
    return await client.post(f"{LEADS}/{lead['id']}/quotations", json=APR | body)


def test_calculation_matches_the_excel_sheets() -> None:
    terms = [
        Term("A", Decimal(30), None),
        Term("B", Decimal(50), None),
        Term("C", Decimal(20), None),
    ]
    # PT. YESUN, sheet IIT IDR: 6 x 21 m, 20% special discount.
    a = compute(
        width_m=Decimal(6), length_m=Decimal(21), area_sqm=None, complimentary_sqm=Decimal(0),
        stand_rate=Decimal(4850000), raw_rate=Decimal(4850000), discount_percent=Decimal(20),
        vat_rate=Decimal(12), vat_base_num=11, vat_base_den=12, terms=terms,
    )  # fmt: skip
    assert (a.charged_sqm, a.discount_amount, a.cost_amount, a.total_amount) == (
        Decimal(126),
        Decimal("122220000.00"),
        Decimal("488880000.00"),
        Decimal("542656800.00"),
    )
    assert a.term_amounts == (
        Decimal("162797040.00"),
        Decimal("271328400.00"),
        Decimal("108531360.00"),
    )


async def test_settings() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    r = await admin.get(url(edition))
    assert r.status_code == 200, r.text
    assert (r.json()["exists"], r.json()["code"], len(r.json()["terms"])) == (False, None, 3)

    bad = SETTINGS | {"terms": [{"label": "All", "percent": "90"}]}
    assert (await admin.put(url(edition), json=bad)).status_code == 422
    twice = SETTINGS | {"rates": SETTINGS["rates"] + [SETTINGS["rates"][0]]}
    assert (await admin.put(url(edition), json=twice)).status_code == 422
    r = await admin.put(url(edition), json=SETTINGS)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["exists"], out["code"], out["next_number"], out["version"]) == (True, "IIT", 113, 1)
    r = await admin.put(url(edition), json=SETTINGS | {"place": "Surabaya", "version": 1})
    assert r.json()["place"] == "Surabaya"
    assert (await admin.put(url(edition), json=SETTINGS | {"version": 1})).status_code == 409

    # Sales read the settings (the form starts from them) but do not change them.
    await sales_role()
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    assert (await sales.get(url(edition))).status_code == 200
    assert (await sales.put(url(edition), json=SETTINGS | {"version": 2})).status_code == 403


async def test_raw_space_quotation_like_the_excel() -> None:
    _edition, admin, lead = await setup()
    r = await admin.post(f"{LEADS}/{lead['id']}/quotations/preview", json=APR)
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["number"] == "113/PNJS/IIT/VII/2026"
    assert (preview["area_sqm"], preview["charged_sqm"]) == ("279.00", "258.00")
    assert (preview["discount_amount"], preview["cost_amount"]) == ("325725000.00", "977175000.00")
    assert (preview["vat_amount"], preview["total_amount"]) == ("107489250.00", "1084664250.00")
    assert [t["amount"] for t in preview["terms"]] == [
        "325399275.00",
        "542332125.00",
        "216932850.00",
    ]
    assert preview["attention"] == "Ms. Novy"
    assert preview["recipient_company"] == "Example Corp"  # the lead's company by default

    # A preview takes no number; Create takes the one shown.
    again = (await admin.post(f"{LEADS}/{lead['id']}/quotations/preview", json=APR)).json()
    assert again["number"] == preview["number"]
    r = await quote(admin, lead)
    assert r.status_code == 201, r.text
    q = r.json()
    assert (q["number"], q["status"], q["total_amount"]) == (
        "113/PNJS/IIT/VII/2026",
        "ISSUED",
        "1084664250.00",
    )
    assert (await quote(admin, lead)).json()["number"] == "114/PNJS/IIT/VII/2026"


async def test_shell_scheme_in_usd() -> None:
    _edition, admin, lead = await setup()
    r = await quote(
        admin, lead, stand_type="SHELL", currency="USD", width_m="3", length_m="3",
        complimentary_sqm="0", discount_percent="15",
    )  # fmt: skip
    assert r.status_code == 201, r.text
    q = r.json()
    # 9 sqm x USD 395, minus 15% of the raw space cost (9 x 365); no VAT in USD.
    assert (q["gross_amount"], q["discount_amount"], q["vat_amount"], q["total_amount"]) == (
        "3555.00",
        "492.75",
        "0.00",
        "3062.25",
    )
    assert q["includes"].startswith("Partition, folding chair")
    # VAT can be switched on.
    q = (await quote(admin, lead, currency="USD", vat=True, complimentary_sqm="0")).json()
    assert q["vat_amount"] != "0.00"


async def test_booth_terms_and_overrides() -> None:
    edition, admin, lead = await setup()
    lead = await opportunity(admin, edition, "booth-q@example.test")
    a01 = (await add_booth(admin, edition, "A01", area_sqm="18")).json()
    body = {"stand_type": "RAW", "booth_id": a01["id"], "stand_rate": "4000000"}
    r = await admin.post(f"{LEADS}/{lead['id']}/quotations", json=body)
    assert r.status_code == 201, r.text
    q = r.json()
    assert (q["booth_code"], q["area_sqm"], q["total_amount"]) == ("A01", "18.00", "79920000.00")
    assert q["discount_label"] is None

    r = await admin.post(
        f"{LEADS}/{lead['id']}/quotations",
        json={"stand_type": "RAW", "area_sqm": "9", "terms": [{"label": "Full", "percent": "60"}]},
    )
    assert r.status_code == 422
    r = await admin.post(
        f"{LEADS}/{lead['id']}/quotations",
        json={"stand_type": "RAW", "booth_code": "Z9", "area_sqm": "9", "complimentary_sqm": "9"},
    )
    assert r.status_code == 422
    assert "complimentary_sqm" in r.json()["error"]["fields"]


async def test_revision_history_and_cancel() -> None:
    _edition, admin, lead = await setup()
    first = (await quote(admin, lead)).json()
    second = (await quote(admin, lead, discount_percent="30", replaces_id=first["id"])).json()
    assert second["replaces_id"] == first["id"]
    history = (await admin.get(f"{LEADS}/{lead['id']}/quotations")).json()
    assert [(h["number"], h["status"]) for h in history] == [
        ("114/PNJS/IIT/VII/2026", "ISSUED"),
        ("113/PNJS/IIT/VII/2026", "SUPERSEDED"),
    ]
    assert history[1]["replaced_by_number"] == "114/PNJS/IIT/VII/2026"
    r = await quote(admin, lead, replaces_id=first["id"])
    assert r.json()["error"]["code"] == "QUOTATION_NOT_ISSUED"

    r = await admin.post(
        f"/api/v1/quotations/{second['id']}/cancel",
        json={"reason": "Company chose a smaller booth", "version": second["version"]},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["cancel_reason"]) == (
        "CANCELLED",
        "Company chose a smaller booth",
    )
    r = await admin.post(
        f"/api/v1/quotations/{second['id']}/cancel",
        json={"reason": "again", "version": r.json()["version"]},
    )
    assert r.status_code == 409


async def test_rules_and_access() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    lead = (await create(admin, edition)).json()
    r = await quote(admin, lead)
    assert r.json()["error"]["code"] == "QUOTATION_SETTINGS_MISSING"
    assert (await admin.put(url(edition), json=SETTINGS)).status_code == 200
    lost = await move(admin, lead, "LOST", lost_reason="No budget")
    assert lost.status_code == 200, lost.text
    assert (await quote(admin, lead)).json()["error"]["code"] == "LEAD_LOST"

    # Another edition with the same code continues the same numbers.
    other = await make_edition()
    other_admin = await admin_for(other)
    assert (await other_admin.put(url(other), json=SETTINGS)).status_code == 200
    other_lead = (await create(other_admin, other, email="other@example.test")).json()
    assert (await quote(other_admin, other_lead)).json()["number"] == "113/PNJS/IIT/VII/2026"
    fresh = (await create(admin, edition, email="fresh@example.test")).json()
    assert (await quote(admin, fresh)).json()["number"] == "114/PNJS/IIT/VII/2026"

    # Out of the caller's editions: not found.
    assert (await other_admin.get(f"{LEADS}/{lead['id']}/quotations")).status_code == 404


# 1 x 1 PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


async def test_signature_and_pdf(storage: MemoryStorage) -> None:
    edition, admin, lead = await setup()
    settings = (await admin.get(url(edition))).json()
    r = await admin.post(
        f"{url(edition)}/signature",
        data={"version": str(settings["version"])},
        files={"file": ("sign.gif", b"GIF89a", "image/gif")},
    )
    assert r.status_code == 422
    broken = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    r = await admin.post(
        f"{url(edition)}/signature",
        data={"version": str(settings["version"])},
        files={"file": ("sign.png", broken, "image/png")},
    )
    assert r.status_code == 422
    r = await admin.post(
        f"{url(edition)}/signature",
        data={"version": str(settings["version"])},
        files={"file": ("sign.png", PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_signature"] is True
    assert (await admin.get(f"{url(edition)}/signature")).content == PNG

    q = (await quote(admin, lead)).json()
    r = await admin.get(f"/api/v1/quotations/{q['id']}/pdf")
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF-")
    assert "Quotation 113-PNJS-IIT-VII-2026.pdf" in r.headers["content-disposition"]
