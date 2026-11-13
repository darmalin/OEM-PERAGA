"""Accepting a quotation and the contract it makes (Phase 4 of docs/EXHIBITOR_QUOTATIONS.md)."""

from typing import Any

from httpx import AsyncClient

from app.core.storage import MemoryStorage
from tests.test_booths import LEADS, add_booth, move
from tests.test_exhibitor_contracts import FIELDS, contract_url, fill, upload
from tests.test_quotations import quote, setup

QUOTATIONS = "/api/v1/quotations"


async def accept(client: AsyncClient, q: dict[str, Any]) -> Any:
    current = (await client.get(f"{QUOTATIONS}/{q['id']}")).json()
    return await client.post(f"{QUOTATIONS}/{q['id']}/accept", json={"version": current["version"]})


async def lead_now(client: AsyncClient, lead: dict[str, Any]) -> dict[str, Any]:
    return dict((await client.get(f"{LEADS}/{lead['id']}")).json())


async def test_accept_at_lead_stage_then_convert(storage: MemoryStorage) -> None:
    edition, admin, lead = await setup()
    b12 = (await add_booth(admin, edition, "B12", area_sqm="126", price="611100000")).json()
    # 6 x 21 m raw space, 20% discount, VAT: IDR 542,656,800 like the Yesun sheet.
    q = (
        await quote(
            admin, lead, booth_id=b12["id"], width_m="6", length_m="21", complimentary_sqm="0",
            discount_percent="20", stand_rate="4850000",
        )
    ).json()  # fmt: skip
    assert q["total_amount"] == "542656800.00"
    r = await accept(admin, q)
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["accepted_at"] is not None) == ("ACCEPTED", True)
    # Still a Lead: no booth yet. Holding the quoted booth later takes the quoted price.
    assert (await lead_now(admin, lead))["booth_id"] is None
    lead = (await move(admin, await lead_now(admin, lead), "OPPORTUNITY")).json()
    r = await admin.put(
        f"{LEADS}/{lead['id']}/booth", json={"booth_id": b12["id"], "version": lead["version"]}
    )
    assert r.json()["booth_price"] == "611100000.00"  # gross, before discount and VAT

    lead = await lead_now(admin, lead)
    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 200, r.text
    c = (await admin.get(contract_url(lead["id"], portal=False))).json()
    assert (c["booth_price"], c["discount_amount"], c["vat_amount"], c["total_amount"]) == (
        "611100000.00",
        "122220000.00",
        "53776800.00",
        "542656800.00",
    )
    assert c["quotation_number"] == q["number"]
    assert [t["amount"] for t in c["payment_terms"]] == [
        "162797040.00",
        "271328400.00",
        "108531360.00",
    ]
    # A discount edit recomputes the VAT on the same tax base.
    c = await fill(admin, contract_url(lead["id"], portal=False), discount_amount="111100000")
    assert (c["vat_amount"], c["total_amount"]) == ("55000000.00", "555000000.00")
    # Payments are counted against the total with VAT.
    pays = (await admin.get(f"{LEADS}/{lead['id']}/payments")).json()
    assert pays["outstanding_amount"] == "555000000.00"


async def test_accept_updates_holder_and_draft_contract(storage: MemoryStorage) -> None:
    edition, admin, lead = await setup()
    lead = (await move(admin, lead, "OPPORTUNITY")).json()
    a01 = (await add_booth(admin, edition, "A01", area_sqm="18")).json()
    lead = (
        await admin.put(
            f"{LEADS}/{lead['id']}/booth", json={"booth_id": a01["id"], "version": lead["version"]}
        )
    ).json()
    r = await admin.post(f"{LEADS}/{lead['id']}/convert", json={"version": lead["version"]})
    assert r.status_code == 200, r.text
    url = contract_url(lead["id"], portal=False)
    assert (await admin.get(url)).json()["vat_amount"] == "0.00"  # before any quotation

    first = (
        await quote(
            admin, lead, booth_id=a01["id"], width_m=None, length_m=None, complimentary_sqm="0"
        )
    ).json()
    second = (
        await quote(admin, lead, booth_id=a01["id"], width_m=None, length_m=None, complimentary_sqm="0", discount_percent="10")
    ).json()  # fmt: skip
    assert (await accept(admin, first)).status_code == 200
    c = (await admin.get(url)).json()
    assert (c["quotation_number"], c["total_amount"]) == (first["number"], first["total_amount"])
    assert (await lead_now(admin, lead))["booth_price"] == first["gross_amount"]

    # Accepting another one replaces it: the first is superseded, the Draft follows.
    assert (await accept(admin, second)).status_code == 200
    assert (await admin.get(f"{QUOTATIONS}/{first['id']}")).json()["status"] == "SUPERSEDED"
    c = (await admin.get(url)).json()
    assert (c["quotation_number"], c["total_amount"]) == (second["number"], second["total_amount"])
    assert (await accept(admin, first)).json()["error"]["code"] == "QUOTATION_NOT_ISSUED"

    # Signed: no quotation changes the contract any more.
    c = await fill(admin, url, **FIELDS)
    assert (await upload(admin, url, c["version"])).status_code == 200
    third = (
        await quote(
            admin, lead, booth_id=a01["id"], width_m=None, length_m=None, complimentary_sqm="0"
        )
    ).json()
    assert (await accept(admin, third)).json()["error"]["code"] == "CONTRACT_SIGNED"
    assert (await admin.get(f"{QUOTATIONS}/{third['id']}")).json()["status"] == "ISSUED"
