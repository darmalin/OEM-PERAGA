"""Free quantities by booth area (Phase 6 of docs/EXHIBITOR_ORDER_FORMS.md, decision O9)."""

from decimal import Decimal
from typing import Any

import pytest

from app.modules.orders.rules import AllowanceTier, free_allowance, free_quantity
from tests.factories import RoleGrant, actor, make_edition
from tests.test_order_forms import URL
from tests.test_order_portal import Setup, setup

ORDERS = "/api/v1/exhibitor-orders"
TIERS = [
    AllowanceTier(Decimal("0"), 1),
    AllowanceTier(Decimal("18"), 2),
    AllowanceTier(Decimal("36"), 4),
]


@pytest.mark.parametrize(
    ("area", "expected"),
    [("9", 1), ("17.99", 1), ("18", 2), ("35", 2), ("36", 4), ("200", 4), (None, 0)],
)
def test_free_allowance(area: str | None, expected: int) -> None:
    assert free_allowance(Decimal(area) if area else None, TIERS) == expected


def test_free_allowance_without_a_tier_for_small_booths() -> None:
    tiers = [AllowanceTier(Decimal("27"), 3)]
    assert free_allowance(Decimal("9"), tiers) == 0
    assert free_allowance(Decimal("27"), tiers) == 3
    assert free_allowance(Decimal("27"), []) == 0


def test_free_quantity() -> None:
    assert free_quantity(5, 2) == 2
    assert free_quantity(1, 2) == 1  # ordering fewer than the allowance: all free
    assert free_quantity(3, 0) == 0
    assert free_quantity(3, -1) == 0


async def set_tiers(s: Setup, code: str, tiers: list[dict[str, Any]]) -> Any:
    item = s.items[code]
    return await s.admin.put(
        f"{URL}/{s.form['id']}/items/{item['id']}/allowances", json={"tiers": tiers}
    )


async def test_allowances_api() -> None:
    s = await setup()
    r = await set_tiers(
        s,
        "E-001",
        [{"min_area_sqm": "18", "free_quantity": 2}, {"min_area_sqm": "0", "free_quantity": 1}],
    )
    assert r.status_code == 200, r.text
    assert r.json()["allowances"] == [
        {"min_area_sqm": "0.00", "free_quantity": 1},
        {"min_area_sqm": "18.00", "free_quantity": 2},
    ]
    items = (await s.admin.get(f"{URL}/{s.form['id']}/items")).json()["items"]
    assert [len(i["allowances"]) for i in items] == [2, 0]
    r = await set_tiers(
        s,
        "E-001",
        [{"min_area_sqm": "9", "free_quantity": 1}, {"min_area_sqm": "9.00", "free_quantity": 2}],
    )
    assert r.status_code == 422
    assert (
        await set_tiers(s, "E-001", [{"min_area_sqm": "9", "free_quantity": 0}])
    ).status_code == 422
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", s.edition.id))
    item = s.items["E-001"]
    r = await agent.put(f"{URL}/{s.form['id']}/items/{item['id']}/allowances", json={"tiers": []})
    assert r.status_code == 403
    assert (await set_tiers(s, "E-001", [])).json()["allowances"] == []


async def test_free_quantity_in_the_portal() -> None:
    s = await setup()  # the exhibitor's booth is 9 m²
    await set_tiers(
        s,
        "E-001",
        [{"min_area_sqm": "0", "free_quantity": 2}, {"min_area_sqm": "18", "free_quantity": 4}],
    )
    detail = await s.detail()
    assert [(i["code"], i["free_quantity"]) for i in detail["items"]] == [
        ("E-001", 2),
        ("E-002", 0),
    ]

    order = (await s.save(await s.draft(), lines=[s.line("E-001", 3), s.line("E-002", 1)])).json()
    assert [(line["free_quantity"], line["amount"]) for line in order["lines"]] == [
        (2, "100.00"),
        (0, "50.00"),
    ]
    assert order["total"] == "150.00"
    sent = (await s.submit(order)).json()
    assert (sent["lines"][0]["free_quantity"], sent["total"]) == (2, "150.00")

    # The allowance is per exhibitor, not per order: a second order pays in full.
    assert (await s.detail())["items"][0]["free_quantity"] == 0
    second = (await s.save(await s.draft(), lines=[s.line("E-001", 1)])).json()
    assert (second["lines"][0]["free_quantity"], second["total"]) == (0, "100.00")

    # Cancelling the first order gives the allowance back to the next one.
    staff = (await s.admin.get(f"{ORDERS}/{sent['id']}")).json()
    r = await s.admin.post(
        f"{ORDERS}/{sent['id']}/cancel",
        json={"reason": "Ordered twice", "version": staff["version"]},
    )
    assert r.status_code == 200, r.text
    quoted = (await s.portal.post(s.url(f"/orders/{second['id']}/quote"))).json()
    assert (quoted["lines"][0]["free_quantity"], quoted["total"]) == (1, "0.00")
    second = (await s.save(second, lines=[s.line("E-001", 1)])).json()
    assert (await s.submit(second)).json()["total"] == "0.00"


async def test_sent_orders_keep_their_free_quantity() -> None:
    s = await setup()
    await set_tiers(s, "E-001", [{"min_area_sqm": "0", "free_quantity": 1}])
    order = (await s.save(await s.draft(), lines=[s.line("E-001", 2)])).json()
    sent = (await s.submit(order)).json()
    await set_tiers(s, "E-001", [])
    staff = (await s.admin.get(f"{ORDERS}/{sent['id']}")).json()
    assert (staff["lines"][0]["free_quantity"], staff["total"]) == (1, "100.00")


async def test_allowances_copy_with_the_form() -> None:
    s = await setup()
    await set_tiers(
        s,
        "E-001",
        [{"min_area_sqm": "0", "free_quantity": 1}, {"min_area_sqm": "27", "free_quantity": 3}],
    )
    target = await make_edition()
    _, both = await actor(
        RoleGrant("EXHIBITION_ADMIN", "EDITION", s.edition.id),
        RoleGrant("EXHIBITION_ADMIN", "EDITION", target.id),
    )
    r = await both.post(
        f"{URL}/copy", json={"from_edition_id": str(s.edition.id), "to_edition_id": str(target.id)}
    )
    assert r.status_code == 200, r.text
    copied = (await both.get(URL, params={"edition_id": str(target.id)})).json()["items"][0]
    items = (await both.get(f"{URL}/{copied['id']}/items")).json()["items"]
    assert [t["free_quantity"] for t in items[0]["allowances"]] == [1, 3]
