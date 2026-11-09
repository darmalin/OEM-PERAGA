"""Order forms in the exhibitor portal (Phase 3 of docs/EXHIBITOR_ORDER_FORMS.md)."""

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from httpx import AsyncClient

from app.core.db import get_sessionmaker
from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition, EditionStatus
from tests.factories import make_edition
from tests.test_exhibitor_contracts import FIELDS, contract_url, fill, portal_exhibitor, upload
from tests.test_exhibitor_leads import admin_for
from tests.test_order_forms import PNG, URL, add_form, add_item

PORTAL = "/api/v1/portal/exhibitors"
PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n%%EOF\n"


def today() -> date:
    return datetime.now(ZoneInfo("Asia/Jakarta")).date()  # make_edition's timezone


async def set_edition(edition: Edition, **values: Any) -> None:
    async with get_sessionmaker()() as session, session.begin():
        row = await session.get(Edition, edition.id)
        assert row is not None
        for key, value in values.items():
            setattr(row, key, value)


def periods(current: str) -> dict[str, date]:
    """Back-to-back periods with today inside `current` (REGULAR, SURCHARGE, ONSITE, or NONE)."""
    t = today()
    starts = {"REGULAR": 0, "SURCHARGE": 1, "ONSITE": 2, "NONE": 3}
    base = t - timedelta(days=10 + 30 * starts[current])
    return {
        "price_regular_from": base,
        "price_regular_to": base + timedelta(days=29),
        "price_surcharge_from": base + timedelta(days=30),
        "price_surcharge_to": base + timedelta(days=59),
        "price_onsite_from": base + timedelta(days=60),
        "price_onsite_to": base + timedelta(days=89),
    }


class Setup:
    def __init__(
        self,
        edition: Edition,
        admin: AsyncClient,
        portal: AsyncClient,
        lead_id: str,
        form: dict[str, Any],
        items: dict[str, dict[str, Any]],
    ) -> None:
        self.edition, self.admin, self.portal, self.lead_id = edition, admin, portal, lead_id
        self.form, self.items = form, items

    def url(self, path: str = "") -> str:
        return f"{PORTAL}/{self.lead_id}{path}"

    async def detail(self, code: str = "04") -> dict[str, Any]:
        r = await self.portal.get(self.url(f"/order-forms/{code}"))
        assert r.status_code == 200, r.text
        return dict(r.json())

    async def draft(self, code: str = "04") -> dict[str, Any]:
        r = await self.portal.post(self.url(f"/order-forms/{code}/orders"))
        assert r.status_code == 201, r.text
        return dict(r.json())

    async def save(self, order: dict[str, Any], **body: Any) -> Any:
        return await self.portal.patch(
            self.url(f"/orders/{order['id']}"), json={"version": order["version"], **body}
        )

    async def submit(self, order: dict[str, Any]) -> Any:
        return await self.portal.post(
            self.url(f"/orders/{order['id']}/submit"), json={"version": order["version"]}
        )

    def line(self, code: str, quantity: int) -> dict[str, Any]:
        return {"item_id": self.items[code]["id"], "quantity": quantity}


async def setup(email: str = "booth-001@example.test") -> Setup:
    edition = await make_edition()
    await set_edition(edition, **periods("REGULAR"))
    admin = await admin_for(edition)
    form = (
        await add_form(
            admin,
            edition,
            "04",
            has_catalog=True,
            allow_custom_items=True,
            attachment_purposes=["FITTING_LOCATION"],
            deadline_on=str(today() + timedelta(days=5)),
        )
    ).json()
    items = {
        "E-001": (await add_item(admin, form, "E-001", price_regular="100", price_surcharge="120", price_onsite="150")).json(),
        "E-002": (await add_item(admin, form, "E-002", name="Socket", price_regular="50", max_quantity=2)).json(),
    }  # fmt: skip
    r = await admin.patch(
        f"{URL}/{form['id']}", json={"is_published": True, "version": form["version"]}
    )
    assert r.status_code == 200, r.text
    portal, lead_id = await portal_exhibitor(admin, edition, email)
    return Setup(edition, admin, portal, lead_id, r.json(), items)


async def test_list_and_detail() -> None:
    s = await setup()
    await add_form(s.admin, s.edition, "07", has_catalog=True)  # not published: hidden
    r = await s.portal.get(s.url("/order-forms"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["price_period"] == "REGULAR"
    assert [(f["code"], f["progress"], f["is_closed"]) for f in body["forms"]] == [
        ("04", "NOT_STARTED", False)
    ]
    detail = await s.detail()
    assert detail["company_name"] == "Example Corp"
    assert detail["booth_code"] == "A01"
    assert [(i["code"], i["unit_price"]) for i in detail["items"]] == [
        ("E-001", "100.00"),
        ("E-002", "50.00"),
    ]
    assert detail["open_order"] is None
    assert (await s.portal.get(s.url("/order-forms/07"))).status_code == 404


async def test_draft_quote_and_submit() -> None:
    s = await setup()
    order = await s.draft()
    assert order["status"] == "DRAFT"
    assert order["order_number"] is None
    r = await s.portal.post(s.url("/order-forms/04/orders"))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ORDER_OPEN"

    r = await s.save(
        order,
        lines=[s.line("E-001", 3), s.line("E-002", 2)],
        custom_lines=[{"name": " Spotlight 300 W ", "size": "300 W", "quantity": 2}],
        remarks=" Near the entrance ",
    )
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["total"] == "400.00"
    assert order["remarks"] == "Near the entrance"
    assert order["unpriced_lines"] == 1
    custom = order["lines"][-1]
    assert (custom["name"], custom["unit_price"], custom["amount"]) == (
        "Spotlight 300 W",
        None,
        None,
    )

    r = await s.portal.post(s.url(f"/orders/{order['id']}/quote"))
    assert r.json()["total"] == "400.00"
    assert r.json()["price_period"] == "REGULAR"

    r = await s.submit(order)
    assert r.status_code == 200, r.text
    sent = r.json()
    assert sent["status"] == "SUBMITTED"
    assert sent["order_number"] == f"{s.edition.code}-O-0001"
    assert sent["price_period"] == "REGULAR"
    assert sent["submitted_at"] is not None
    assert sent["waiting_for_contract"] is True  # contract still Draft (decision O2)

    assert (await s.save(sent, lines=[])).json()["error"]["code"] == "ORDER_SENT"
    assert (await s.submit(sent)).json()["error"]["code"] == "ORDER_SENT"
    forms = (await s.portal.get(s.url("/order-forms"))).json()["forms"]
    assert (forms[0]["progress"], forms[0]["sent_orders"], forms[0]["open_order_id"]) == (
        "SUBMITTED",
        1,
        None,
    )
    # An extra order on the same form is a new draft with its own number later.
    second = await s.draft()
    second = (await s.save(second, lines=[s.line("E-002", 1)])).json()
    assert (await s.submit(second)).json()["order_number"] == f"{s.edition.code}-O-0002"
    detail = await s.detail()
    assert [o["order_number"] for o in detail["sent_orders"]] == [
        f"{s.edition.code}-O-0002",
        f"{s.edition.code}-O-0001",
    ]


async def test_signed_contract_clears_the_wait() -> None:
    s = await setup()
    url = contract_url(s.lead_id)
    contract = await fill(s.portal, url, **FIELDS)
    assert (await upload(s.portal, url, contract["version"])).status_code == 200
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 1)])).json()
    assert (await s.submit(order)).json()["waiting_for_contract"] is False


async def test_price_period_is_fixed_on_submit() -> None:
    s = await setup()
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 2)])).json()
    assert order["total"] == "200.00"  # regular while saving

    await set_edition(s.edition, **periods("SURCHARGE"))
    quoted = (await s.portal.post(s.url(f"/orders/{order['id']}/quote"))).json()
    assert (quoted["price_period"], quoted["total"]) == ("SURCHARGE", "240.00")
    sent = (await s.submit(order)).json()
    assert (sent["price_period"], sent["total"], sent["lines"][0]["unit_price"]) == (
        "SURCHARGE",
        "240.00",
        "120.00",
    )
    # Later catalog edits do not reach a sent order.
    item = s.items["E-001"]
    await s.admin.patch(
        f"{URL}/{s.form['id']}/items/{item['id']}",
        json={"price_surcharge": "999", "version": item["version"]},
    )
    detail = await s.detail()
    assert detail["sent_orders"][0]["total"] == "240.00"
    assert detail["items"][0]["unit_price"] == "999.00"

    await set_edition(s.edition, **periods("ONSITE"))
    assert (await s.detail())["items"][0]["unit_price"] == "150.00"

    await set_edition(s.edition, **periods("NONE"))
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 1)])).json()
    assert order["total"] == "100.00"  # regular as an estimate while ordering is not open
    r = await s.submit(order)
    assert r.json()["error"]["code"] == "ORDERING_NOT_OPEN"


async def test_draft_rules() -> None:
    s = await setup()
    order = await s.draft()
    r = await s.save(order, lines=[s.line("E-002", 3)])
    assert r.status_code == 422
    assert "At most 2" in str(r.json()["error"]["fields"])
    r = await s.save(order, lines=[s.line("E-001", 1), s.line("E-001", 2)])
    assert r.status_code == 422
    r = await s.save(order, lines=[{"item_id": s.items["E-001"]["id"], "quantity": 0}])
    assert r.status_code == 422
    r = await s.save(order, lines=[s.line("E-001", 1)], total="1")
    assert r.status_code == 422  # the portal never sends prices or totals
    r = await s.save(order, custom_lines=[{"name": "  ", "quantity": 1}])
    assert r.status_code == 422
    r = await s.save(order, lines=[], version=99)
    assert r.status_code == 409

    assert (await s.submit(order)).json()["error"]["code"] == "ORDER_EMPTY"

    # An item deactivated after saving blocks the submit until it is removed.
    order = (await s.save(order, lines=[s.line("E-001", 1)])).json()
    item = s.items["E-001"]
    r = await s.admin.patch(
        f"{URL}/{s.form['id']}/items/{item['id']}",
        json={"is_active": False, "version": item["version"]},
    )
    assert r.status_code == 200, r.text
    r = await s.submit(order)
    assert r.status_code == 422
    assert "no longer available" in str(r.json()["error"]["fields"])


async def test_catalog_only_and_closed_forms() -> None:
    s = await setup()
    plain = (await add_form(s.admin, s.edition, "05", has_catalog=True)).json()
    item = (await add_item(s.admin, plain, "C-001")).json()
    await s.admin.patch(f"{URL}/{plain['id']}", json={"is_published": True, "version": 1})
    order = await s.draft("05")
    r = await s.save(order, custom_lines=[{"name": "Something else", "quantity": 1}])
    assert r.json()["error"]["fields"]["custom_lines"]
    order = (await s.save(order, lines=[{"item_id": item["id"], "quantity": 1}])).json()
    # Another form's item is not on this form.
    r = await s.save(order, lines=[s.line("E-001", 1)])
    assert r.status_code == 422

    await set_edition(s.edition, order_expired_on=today() - timedelta(days=1))
    assert (await s.portal.post(s.url("/order-forms/04/orders"))).json()["error"][
        "code"
    ] == "FORM_CLOSED"
    assert (await s.submit(order)).json()["error"]["code"] == "FORM_CLOSED"
    assert (await s.detail("05"))["is_closed"] is True
    # The form's own date wins over the edition's.
    form = (await s.admin.get(f"{URL}/{plain['id']}")).json()
    await s.admin.patch(
        f"{URL}/{plain['id']}", json={"closes_on": str(today()), "version": form["version"]}
    )
    assert (await s.submit(order)).status_code == 200


async def test_delete_draft_only() -> None:
    s = await setup()
    order = await s.draft()
    assert (await s.portal.delete(s.url(f"/orders/{order['id']}"))).status_code == 204
    assert (await s.detail())["open_order"] is None
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 1)])).json()
    sent = (await s.submit(order)).json()
    r = await s.portal.delete(s.url(f"/orders/{sent['id']}"))
    assert r.status_code == 409


async def test_access() -> None:
    s = await setup()
    other = await setup("booth-002@example.test")
    order = await s.draft()
    # Another exhibitor sees neither the order nor the lead.
    assert (await other.portal.get(other.url(f"/orders/{order['id']}/quote"))).status_code == 405
    r = await other.portal.post(other.url(f"/orders/{order['id']}/quote"))
    assert r.status_code == 404
    r = await other.portal.get(f"{PORTAL}/{s.lead_id}/order-forms")
    assert r.status_code == 404
    # Staff sessions do not open the portal; writes need the portal's CSRF token.
    assert (await s.admin.get(s.url("/order-forms"))).status_code == 401
    r = await s.portal.post(s.url("/order-forms/04/orders"), headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403


async def test_archived_edition_is_read_only() -> None:
    s = await setup()
    order = await s.draft()
    await set_edition(s.edition, status=EditionStatus.ARCHIVED)
    assert (await s.save(order, lines=[s.line("E-001", 1)])).json()["error"][
        "code"
    ] == "EDITION_ARCHIVED"
    assert (await s.portal.get(s.url("/order-forms"))).status_code == 200


async def test_attachments_and_pictures(storage: MemoryStorage) -> None:
    s = await setup()
    order = await s.draft()
    files_url = s.url(f"/orders/{order['id']}/files")

    def attach(name: str, data: bytes, mime: str, purpose: str, version: int) -> Any:
        return s.portal.post(
            files_url,
            data={"purpose": purpose, "version": str(version)},
            files={"file": (name, data, mime)},
        )

    r = await attach("layout.pdf", PDF, "application/pdf", "FITTING_LOCATION", order["version"])
    assert r.status_code == 200, r.text
    order = r.json()
    attached = order["files"][0]
    assert (attached["purpose"], attached["file_name"]) == ("FITTING_LOCATION", "layout.pdf")
    r = await s.portal.get(f"{files_url}/{attached['id']}")
    assert r.status_code == 200
    assert r.content == PDF

    r = await attach("logo.png", PNG, "image/png", "LOGO", order["version"])
    assert r.status_code == 422  # this form does not take a logo
    r = await attach(
        "layout.pdf", b"not a pdf", "application/pdf", "FITTING_LOCATION", order["version"]
    )
    assert r.status_code == 422
    r = await attach("layout.exe", PDF, "application/pdf", "FITTING_LOCATION", order["version"])
    assert r.status_code == 422

    # A file alone is enough to send; remove it again first.
    r = await s.portal.delete(f"{files_url}/{attached['id']}", params={"version": order["version"]})
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["files"] == []

    order = (await s.save(order, custom_lines=[{"name": "Spotlight", "quantity": 1}])).json()
    line = order["lines"][0]
    image_url = s.url(f"/orders/{order['id']}/lines/{line['id']}/image")
    r = await s.portal.post(
        image_url,
        data={"version": str(order["version"])},
        files={"file": ("spot.png", PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    order = r.json()
    assert order["lines"][0]["has_image"] is True
    assert (await s.portal.get(image_url)).content == PNG
    # Saving again with the line's id keeps its picture.
    order = (
        await s.save(order, custom_lines=[{"id": line["id"], "name": "Spotlight", "quantity": 2}])
    ).json()
    assert order["lines"][0]["has_image"] is True

    # Catalog pictures reach the portal through its own route.
    item = s.items["E-001"]
    r = await s.admin.post(
        f"{URL}/{s.form['id']}/items/{item['id']}/image",
        files={"file": ("lamp.png", PNG, "image/png")},
        data={"version": str(item["version"])},
    )
    assert r.status_code == 200, r.text
    r = await s.portal.get(s.url(f"/order-forms/04/items/{item['id']}/image"))
    assert r.status_code == 200
    assert r.content == PNG


async def test_not_required() -> None:
    s = await setup()
    url = s.url("/order-forms/04/not-required")
    r = await s.portal.put(url)
    assert r.status_code == 200, r.text
    assert (r.json()["not_required"], r.json()["progress"]) == (True, "NOT_REQUIRED")
    assert (await s.portal.put(url)).status_code == 200  # again: no change

    # Sending an order answers the question.
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 1)])).json()
    await s.submit(order)
    detail = await s.detail()
    assert (detail["not_required"], detail["progress"]) == (False, "SUBMITTED")
    r = await s.portal.put(url)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "FORM_HAS_ORDERS"

    other = await setup("booth-002@example.test")
    other_url = other.url("/order-forms/04/not-required")
    await other.portal.put(other_url)
    r = await other.portal.delete(other_url)
    assert (r.json()["not_required"], r.json()["progress"]) == (False, "NOT_STARTED")
