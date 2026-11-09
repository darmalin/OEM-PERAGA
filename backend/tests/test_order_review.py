"""Staff review of exhibitor orders (Phase 4 of docs/EXHIBITOR_ORDER_FORMS.md)."""

import io
from typing import Any

from openpyxl import load_workbook

from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import EditionStatus
from tests.factories import RoleGrant, actor
from tests.test_booths import add_booth, assign
from tests.test_exhibitor_contracts import FIELDS, contract_url, fill, upload
from tests.test_exhibitor_leads import SALES_ROLE, sales_role
from tests.test_order_forms import PNG
from tests.test_order_portal import Setup, set_edition, setup

URL = "/api/v1/exhibitor-orders"


async def sent(s: Setup, custom: bool = False, **lines: int) -> dict[str, Any]:
    """An order the exhibitor sent; quantities by item code."""
    order = await s.draft()
    body: dict[str, Any] = {"lines": [s.line(code, qty) for code, qty in lines.items()]}
    if custom:
        body["custom_lines"] = [{"name": "Spotlight 300 W", "quantity": 2}]
    order = (await s.save(order, **body)).json()
    r = await s.submit(order)
    assert r.status_code == 200, r.text
    return dict(r.json())


async def sign(s: Setup) -> None:
    url = contract_url(s.lead_id)
    contract = await fill(s.portal, url, **FIELDS)
    assert (await upload(s.portal, url, contract["version"])).status_code == 200


async def staff_view(s: Setup, order_id: str) -> dict[str, Any]:
    r = await s.admin.get(f"{URL}/{order_id}")
    assert r.status_code == 200, r.text
    return dict(r.json())


async def decide(s: Setup, order: dict[str, Any], decision: str, notes: str | None = None) -> Any:
    body = {"decision": decision, "notes": notes, "version": order["version"]}
    return await s.admin.post(f"{URL}/{order['id']}/review", json=body)


async def test_queue_and_detail() -> None:
    s = await setup()
    await s.draft()  # a draft is the exhibitor's own and never listed
    r = await s.admin.get(URL, params={"edition_id": str(s.edition.id)})
    assert r.json()["total"] == 0
    await s.portal.delete(s.url(f"/orders/{(await s.detail())['open_order']['id']}"))

    order = await sent(s, custom=True, **{"E-001": 2})
    r = await s.admin.get(URL, params={"edition_id": str(s.edition.id)})
    assert r.status_code == 200, r.text
    [row] = r.json()["items"]
    assert (row["order_number"], row["company_name"], row["booth_code"], row["form_code"]) == (
        order["order_number"],
        "Example Corp",
        "A01",
        "04",
    )
    assert (row["status"], row["total"], row["unpriced_lines"]) == ("SUBMITTED", "200.00", 1)
    assert (row["waiting_for_contract"], row["booth_changed"]) == (True, False)
    for params in [{"status": "APPROVED"}, {"q": "nobody"}, {"form_id": s.items["E-001"]["id"]}]:
        r = await s.admin.get(URL, params={"edition_id": str(s.edition.id), **params})
        assert r.json()["total"] == 0, params
    r = await s.admin.get(
        URL, params={"edition_id": str(s.edition.id), "q": order["order_number"].lower()}
    )
    assert r.json()["total"] == 1
    r = await s.admin.get(URL, params={"edition_id": str(s.edition.id), "status": "DRAFT"})
    assert r.status_code == 422

    detail = await staff_view(s, order["id"])
    assert (
        detail["price_period"],
        detail["booth_code_at_submit"],
        detail["area_sqm_at_submit"],
    ) == (
        "REGULAR",
        "A01",
        "9.00",
    )
    assert [line["name"] for line in detail["lines"]] == ["Fluorescent lamp", "Spotlight 300 W"]


async def test_price_extra_items_then_approve() -> None:
    s = await setup()
    order = await staff_view(s, (await sent(s, custom=True, **{"E-001": 2}))["id"])
    custom = order["lines"][1]

    r = await decide(s, order, "APPROVED")
    assert r.json()["error"]["code"] == "UNPRICED_LINES"
    catalog = order["lines"][0]
    r = await s.admin.patch(
        f"{URL}/{order['id']}/lines/{catalog['id']}",
        json={"unit_price": "1", "version": order["version"]},
    )
    assert r.json()["error"]["code"] == "CATALOG_PRICE"
    r = await s.admin.patch(
        f"{URL}/{order['id']}/lines/{custom['id']}",
        json={"unit_price": "75000", "version": order["version"]},
    )
    assert r.status_code == 200, r.text
    order = r.json()
    assert (order["total"], order["unpriced_lines"]) == ("150200.00", 0)
    assert order["lines"][1]["amount"] == "150000.00"

    # Costs money and the contract is still Draft (decision O2).
    r = await decide(s, order, "APPROVED")
    assert r.json()["error"]["code"] == "CONTRACT_NOT_SIGNED"
    await sign(s)
    order = await staff_view(s, order["id"])
    assert order["waiting_for_contract"] is False
    r = await decide(s, order, "APPROVED", " Delivered on day one ")
    assert r.status_code == 200, r.text
    approved = r.json()
    assert (approved["status"], approved["review_notes"], approved["reviewed_by_name"]) == (
        "APPROVED",
        "Delivered on day one",
        approved["reviewed_by_name"],
    )
    assert approved["reviewed_by_name"]
    assert (await decide(s, approved, "RETURNED", "x")).json()["error"][
        "code"
    ] == "ORDER_NOT_SUBMITTED"
    r = await s.admin.patch(
        f"{URL}/{order['id']}/lines/{custom['id']}",
        json={"unit_price": "1", "version": approved["version"]},
    )
    assert r.json()["error"]["code"] == "ORDER_NOT_SUBMITTED"

    # The exhibitor sees the confirmed total and the staff price of the extra item.
    portal_order = (await s.detail())["sent_orders"][0]
    assert (portal_order["status"], portal_order["total"], portal_order["unpriced_lines"]) == (
        "APPROVED",
        "150200.00",
        0,
    )


async def test_free_order_needs_no_contract() -> None:
    s = await setup()
    plain = (
        await s.admin.post(
            "/api/v1/order-forms",
            json={
                "edition_id": str(s.edition.id),
                "code": "08",
                "title": "Exhibit Details",
                "attachment_purposes": ["OTHER"],
                "is_published": True,
            },
        )
    ).json()
    assert plain["is_published"] is True
    draft = (await s.portal.post(s.url("/order-forms/08/orders"))).json()
    r = await s.portal.post(
        s.url(f"/orders/{draft['id']}/files"),
        data={"purpose": "OTHER", "version": str(draft["version"])},
        files={"file": ("specs.pdf", b"%PDF-1.7\n%%EOF\n", "application/pdf")},
    )
    assert r.status_code == 200, r.text
    order = (await s.submit(r.json())).json()
    assert order["total"] == "0.00"
    order = await staff_view(s, order["id"])
    assert (await decide(s, order, "APPROVED")).status_code == 200


async def test_return_and_resubmit() -> None:
    s = await setup()
    order = await staff_view(s, (await sent(s, **{"E-001": 1}))["id"])
    r = await decide(s, order, "RETURNED")
    assert r.status_code == 422
    assert "notes" in r.json()["error"]["fields"]
    r = await decide(s, order, "RETURNED", "Spotlights instead of lamps, please.")
    assert r.status_code == 200, r.text

    # Back in the portal: open again with the reason, then sent again with the same number.
    detail = await s.detail()
    returned = detail["open_order"]
    assert (returned["status"], returned["review_notes"]) == (
        "RETURNED",
        "Spotlights instead of lamps, please.",
    )
    assert detail["progress"] == "IN_PROGRESS"
    returned = (await s.save(returned, lines=[s.line("E-002", 2)])).json()
    again = (await s.submit(returned)).json()
    assert (again["status"], again["order_number"], again["total"]) == (
        "SUBMITTED",
        order["order_number"],
        "100.00",
    )


async def test_extra_item_price_survives_a_return() -> None:
    s = await setup()
    order = await staff_view(s, (await sent(s, custom=True, **{"E-001": 1}))["id"])
    custom = order["lines"][1]
    r = await s.admin.patch(
        f"{URL}/{order['id']}/lines/{custom['id']}",
        json={"unit_price": "75000", "version": order["version"]},
    )
    r = await decide(s, r.json(), "RETURNED", "One more lamp, please.")
    assert r.status_code == 200, r.text
    returned = (await s.detail())["open_order"]
    kept = {"id": custom["id"], "name": "Spotlight 300 W", "quantity": 3}
    again = (await s.save(returned, lines=[s.line("E-001", 2)], custom_lines=[kept])).json()
    assert (again["lines"][1]["unit_price"], again["lines"][1]["amount"], again["total"]) == (
        "75000.00",
        "225000.00",
        "225200.00",
    )
    # A changed description needs a new price from staff.
    renamed = (
        await s.save(again, lines=[], custom_lines=[{**kept, "name": "Spotlight 500 W"}])
    ).json()
    assert (renamed["lines"][0]["unit_price"], renamed["unpriced_lines"]) == (None, 1)


async def test_cancel() -> None:
    s = await setup()
    order = await staff_view(s, (await sent(s, **{"E-001": 1}))["id"])
    url = f"{URL}/{order['id']}/cancel"
    assert (
        await s.admin.post(url, json={"reason": " ", "version": order["version"]})
    ).status_code == 422
    r = await s.admin.post(url, json={"reason": "Ordered twice", "version": order["version"]})
    assert r.status_code == 200, r.text
    cancelled = r.json()
    assert (cancelled["status"], cancelled["cancel_reason"]) == ("CANCELLED", "Ordered twice")
    r = await s.admin.post(url, json={"reason": "Again", "version": cancelled["version"]})
    assert r.json()["error"]["code"] == "ORDER_CANCELLED"
    assert (await s.detail())["sent_orders"][0]["cancel_reason"] == "Ordered twice"
    assert (await s.detail())["progress"] == "NOT_STARTED"


async def test_stale_version_and_archived_edition() -> None:
    s = await setup()
    order = await staff_view(s, (await sent(s, **{"E-001": 1}))["id"])
    stale = {**order, "version": order["version"] - 1}
    assert (await decide(s, stale, "RETURNED", "x")).status_code == 409
    await set_edition(s.edition, status=EditionStatus.ARCHIVED)
    assert (await decide(s, order, "RETURNED", "x")).json()["error"]["code"] == "EDITION_ARCHIVED"
    assert (await s.admin.get(f"{URL}/{order['id']}")).status_code == 200


async def test_booth_changed_since_submit() -> None:
    s = await setup()
    order = await sent(s, **{"E-001": 1})
    # The contract is Draft, so staff may still move the exhibitor's booth.
    a02 = (await add_booth(s.admin, s.edition, "A02")).json()
    lead = (await s.admin.get(f"/api/v1/exhibitor-leads/{s.lead_id}")).json()
    assert (await assign(s.admin, lead, a02["id"])).status_code == 200
    detail = await staff_view(s, order["id"])
    assert (detail["booth_changed"], detail["booth_code"], detail["booth_code_at_submit"]) == (
        True,
        "A02",
        "A01",
    )


async def test_access() -> None:
    s = await setup()
    order = await sent(s, **{"E-001": 1})
    other = await setup("booth-002@example.test")
    # Another edition's admin sees nothing of it.
    assert (await other.admin.get(f"{URL}/{order['id']}")).status_code == 404
    r = await other.admin.get(URL, params={"edition_id": str(s.edition.id)})
    assert r.status_code == 404

    # Sales with own leads only: the converted lead has no owner, so it is out of their scope.
    await sales_role()
    _, owned = await actor(RoleGrant(SALES_ROLE, "OWNED", s.edition.id))
    r = await owned.get(URL, params={"edition_id": str(s.edition.id)})
    assert (r.status_code, r.json()["total"]) == (200, 0)
    assert (await owned.get(f"{URL}/{order['id']}")).status_code == 404
    # Edition-wide sales can read but not review.
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", s.edition.id))
    assert (await sales.get(f"{URL}/{order['id']}")).status_code == 200
    r = await sales.post(f"{URL}/{order['id']}/review", json={"decision": "APPROVED", "version": 1})
    assert r.status_code == 403
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", s.edition.id))
    assert (await agent.get(URL, params={"edition_id": str(s.edition.id)})).status_code == 403


async def test_lead_tab() -> None:
    s = await setup()
    await s.admin.post(
        "/api/v1/order-forms",
        json={
            "edition_id": str(s.edition.id),
            "code": "01",
            "title": "E-Directory",
            "details_type": "directory_listing",
            "is_published": True,
        },
    )
    await s.portal.put(s.url("/order-forms/01/not-required"))
    order = await sent(s, **{"E-001": 1})
    r = await s.admin.get(f"/api/v1/exhibitor-leads/{s.lead_id}/orders")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [(f["code"], f["progress"]) for f in body["forms"]] == [
        ("01", "NOT_REQUIRED"),
        ("04", "SUBMITTED"),
    ]
    assert [o["order_number"] for o in body["orders"]] == [order["order_number"]]


async def test_files_and_export(storage: MemoryStorage) -> None:
    s = await setup()
    draft = await s.draft()
    draft = (
        await s.save(
            draft,
            lines=[s.line("E-001", 2)],
            custom_lines=[{"name": "LED strip", "quantity": 1}],
            remarks="Near the door",
        )
    ).json()
    r = await s.portal.post(
        s.url(f"/orders/{draft['id']}/files"),
        data={"purpose": "FITTING_LOCATION", "version": str(draft["version"])},
        files={"file": ("layout.pdf", b"%PDF-1.7\n%%EOF\n", "application/pdf")},
    )
    draft = r.json()
    line = draft["lines"][1]
    r = await s.portal.post(
        s.url(f"/orders/{draft['id']}/lines/{line['id']}/image"),
        data={"version": str(draft["version"])},
        files={"file": ("led.png", PNG, "image/png")},
    )
    order = (await s.submit(r.json())).json()
    detail = await staff_view(s, order["id"])
    f = detail["files"][0]
    r = await s.admin.get(f"{URL}/{order['id']}/files/{f['id']}")
    assert (r.status_code, r.content) == (200, b"%PDF-1.7\n%%EOF\n")
    r = await s.admin.get(f"{URL}/{order['id']}/lines/{line['id']}/image")
    assert (r.status_code, r.content) == (200, PNG)

    r = await s.admin.get(
        f"{URL}/export", params={"edition_id": str(s.edition.id), "form_id": s.form["id"]}
    )
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content)).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0][:4] == ("Order No.", "Status", "Company", "Booth")
    assert [(row[0], row[7], row[9], row[12]) for row in rows[1:]] == [
        (order["order_number"], "Fluorescent lamp", 2, 200),
        (order["order_number"], "LED strip", 1, None),
    ]
