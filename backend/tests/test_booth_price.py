"""Booth typed in while choosing, and the agreed booth price (Phase 1 of
docs/EXHIBITOR_QUOTATIONS.md)."""

from typing import Any

from httpx import AsyncClient

from app.core.storage import MemoryStorage
from tests.factories import RoleGrant, actor, make_edition
from tests.test_booths import LEADS, add_booth, booths, opportunity
from tests.test_exhibitor_contracts import FIELDS, contract_url, fill, upload
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, sales_role


async def hold(client: AsyncClient, lead: dict[str, Any], **body: Any) -> Any:
    current = (await client.get(f"{LEADS}/{lead['id']}")).json()
    return await client.put(
        f"{LEADS}/{lead['id']}/booth", json=body | {"version": current["version"]}
    )


async def test_new_booth_is_added_and_held() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    lead = await opportunity(admin, edition, "price-001@example.test")
    new = {"code": " C9 ", "hall": "Hall C", "area_sqm": "126", "price": "611100000"}
    r = await hold(admin, lead, new_booth=new)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (
        out["booth_code"],
        out["booth_price"],
        out["booth_list_price"],
        out["booth_currency"],
    ) == (
        "C9",
        "611100000.00",
        "611100000.00",
        "IDR",
    )
    listed = await booths(admin, edition, q="C9")
    assert [(b["code"], b["is_available"]) for b in listed] == [("C9", False)]

    # The same code again is refused; a booth and a new booth together too.
    other = await opportunity(admin, edition, "price-002@example.test")
    r = await hold(admin, other, new_booth=new)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_BOOTH_CODE"
    a01 = (await add_booth(admin, edition, "A01")).json()
    r = await hold(admin, other, booth_id=a01["id"], new_booth=new | {"code": "C10"})
    assert r.status_code == 422


async def test_agreed_price() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    a01 = (await add_booth(admin, edition, "A01")).json()  # 15,000,000
    lead = await opportunity(admin, edition, "price-003@example.test")

    out = (await hold(admin, lead, booth_id=a01["id"], price="12500000")).json()
    assert (out["booth_price"], out["booth_list_price"]) == ("12500000.00", "15000000.00")
    # Price only, same booth.
    out = (await hold(admin, lead, booth_id=a01["id"], price="13000000")).json()
    assert out["booth_price"] == "13000000.00"
    # No price keeps the agreed one; a list price edit does not touch it.
    r = await admin.patch(
        f"/api/v1/booths/{a01['id']}", json={"price": "16000000", "version": a01["version"]}
    )
    assert r.status_code == 200, r.text
    out = (await hold(admin, lead, booth_id=a01["id"])).json()
    assert (out["booth_price"], out["booth_list_price"]) == ("13000000.00", "16000000.00")
    # Moving to another booth takes that booth's list price unless one is given.
    a02 = (await add_booth(admin, edition, "A02", price="9000000")).json()
    out = (await hold(admin, lead, booth_id=a02["id"])).json()
    assert out["booth_price"] == "9000000.00"
    # Releasing clears both.
    out = (await hold(admin, lead, booth_id=None)).json()
    assert (out["booth_id"], out["booth_price"]) == (None, None)
    assert (await hold(admin, lead, booth_id=a01["id"], price="-1")).status_code == 422


async def test_contract_takes_and_edits_the_price(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    a01 = (await add_booth(admin, edition, "A01")).json()
    lead = await opportunity(admin, edition, "price-004@example.test")
    lead = (await hold(admin, lead, booth_id=a01["id"], price="14000000")).json()
    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 200, r.text

    staff_url = contract_url(lead["id"], portal=False)
    contract = (await admin.get(staff_url)).json()
    assert (contract["booth_price"], contract["total_amount"]) == ("14000000.00", "14000000.00")

    contract = await fill(admin, staff_url, booth_price="13500000", discount_amount="500000")
    assert (contract["booth_price"], contract["total_amount"]) == ("13500000.00", "13000000.00")
    assert (await admin.get(f"{LEADS}/{lead['id']}")).json()["booth_price"] == "13500000.00"
    r = await admin.patch(staff_url, json={"booth_price": "400000", "version": contract["version"]})
    assert r.status_code == 422  # below the discount
    assert "discount_amount" in r.json()["error"]["fields"]

    # The lead's price edit reaches the DRAFT contract; a signed one is locked.
    out = (await hold(admin, lead, booth_id=a01["id"], price="13800000")).json()
    assert out["booth_price"] == "13800000.00"
    contract = (await admin.get(staff_url)).json()
    assert (contract["booth_price"], contract["total_amount"]) == ("13800000.00", "13300000.00")
    contract = await fill(admin, staff_url, **FIELDS)
    assert (await upload(admin, staff_url, contract["version"])).status_code == 200
    r = await hold(admin, lead, booth_id=a01["id"], price="1")
    assert r.json()["error"]["code"] == "CONTRACT_SIGNED"


async def test_only_booth_managers_add_booths() -> None:
    edition = await make_edition()
    await sales_role()
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    lead = await opportunity(sales, edition, "price-005@example.test")
    r = await hold(sales, lead, new_booth={"code": "S1", "area_sqm": "9", "price": "1"})
    assert r.status_code == 403
    # Choosing a listed booth and agreeing its price stays open to sales.
    admin = await admin_for(edition)
    a01 = (await add_booth(admin, edition, "A01")).json()
    r = await hold(sales, lead, booth_id=a01["id"], price="14000000")
    assert r.status_code == 200, r.text
