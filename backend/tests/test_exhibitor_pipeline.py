"""Sales pipeline summary of an edition (phase 8)."""

from typing import Any

from httpx import AsyncClient

from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition
from tests.factories import RoleGrant, actor, make_edition
from tests.test_booths import add_booth
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, create, move, sales_role
from tests.test_exhibitor_payments import pay, review, signed
from tests.test_exhibitor_portal import exhibitor

URL = "/api/v1/exhibitor-leads/pipeline"


async def pipeline(client: AsyncClient, edition: Edition) -> dict[str, Any]:
    r = await client.get(URL, params={"edition_id": str(edition.id)})
    assert r.status_code == 200, r.text
    return dict(r.json())


def stages(p: dict[str, Any]) -> dict[str, int]:
    return {s["stage"]: s["count"] for s in p["stages"]}


async def test_empty_edition() -> None:
    edition = await make_edition()
    p = await pipeline(await admin_for(edition), edition)
    assert stages(p) == {"LEAD": 0, "OPPORTUNITY": 0, "EXHIBITOR": 0, "LOST": 0}
    assert (p["draft_contracts"], p["booths_for_sale"], p["booths_held"], p["money"]) == (
        0,
        0,
        0,
        [],
    )


async def test_counts_and_money(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    _, lead_id = await signed(admin, edition)  # A01, 15,000,000, SIGNED
    await exhibitor(admin, edition, "booth-002@example.test", "A02")  # DRAFT contract
    await add_booth(admin, edition, "A03")
    await add_booth(admin, edition, "Z99", is_active=False)
    await create(admin, edition, email="sales-100@example.test")
    lost = (await create(admin, edition, email="sales-101@example.test")).json()
    await move(admin, lost, "LOST", lost_reason="No budget")

    deposit = (await pay(admin, lead_id, "5000000")).json()
    await review(admin, lead_id, deposit, "VERIFIED")
    await pay(admin, lead_id, "4000000")  # pending
    rejected = (await pay(admin, lead_id, "1000000")).json()
    await review(admin, lead_id, rejected, "REJECTED", notes="Bounced")

    p = await pipeline(admin, edition)
    assert stages(p) == {"LEAD": 1, "OPPORTUNITY": 0, "EXHIBITOR": 2, "LOST": 1}
    assert (p["draft_contracts"], p["booths_for_sale"], p["booths_held"]) == (1, 3, 2)
    assert p["money"] == [
        {
            "currency": "IDR",
            "signed_contracts": 1,
            "signed_value": "15000000.00",
            "verified_amount": "5000000.00",
            "pending_amount": "4000000.00",
            "outstanding_amount": "10000000.00",
            "paid_contracts": 0,
        }
    ]

    rest = (await pay(admin, lead_id, "6000000")).json()
    await review(admin, lead_id, rest, "VERIFIED")
    money = (await pipeline(admin, edition))["money"][0]
    assert (money["outstanding_amount"], money["paid_contracts"]) == ("4000000.00", 0)


async def test_scope_and_permission(storage: MemoryStorage) -> None:
    edition, other = await make_edition(), await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    await signed(admin, edition)

    # Own Leads scope counts only the caller's leads; booths stay edition-wide.
    _, owned = await actor(RoleGrant(SALES_ROLE, "OWNED", edition.id))
    await create(owned, edition, email="sales-200@example.test")
    p = await pipeline(owned, edition)
    assert stages(p)["LEAD"] == 1 and stages(p)["EXHIBITOR"] == 0
    assert p["money"] == [] and p["booths_held"] == 1

    r = await owned.get(URL, params={"edition_id": str(other.id)})
    assert r.status_code == 404
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))
    assert (await agent.get(URL, params={"edition_id": str(edition.id)})).status_code == 403
