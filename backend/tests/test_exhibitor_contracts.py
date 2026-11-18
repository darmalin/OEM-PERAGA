"""Contract filled and signed in the portal, viewed by staff (phase 5)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.audit import AuditLog
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition
from app.modules.exhibitions.rules import EditionStatus
from app.modules.exhibitors.models import ExhibitorContract
from tests.factories import RoleGrant, actor, make_edition
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, sales_role
from tests.test_exhibitor_portal import LEADS, PORTAL, accept, exhibitor, token_of

PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n%%EOF\n"
FIELDS = {
    "pic_name": "Budi Santoso",
    "company_address": "Jl. Sudirman 1, Jakarta",
    "tax_id_type": "NPWP",
    "tax_id": "01.234.567.8-901.000",
}
PNG = b"\x89PNG\r\n\x1a\n card photo"


async def portal_exhibitor(
    admin: AsyncClient, edition: Edition, email: str = "booth-001@example.test", code: str = "A01"
) -> tuple[AsyncClient, str]:
    """Converted exhibitor signed in to the portal. Returns (portal client, lead id)."""
    converted = await exhibitor(admin, edition, email, code)
    client, r = await accept(token_of(converted["invitation"]))
    assert r.status_code == 200, r.text
    return client, converted["lead"]["id"]


def contract_url(lead_id: str, portal: bool = True) -> str:
    return f"{PORTAL}/exhibitors/{lead_id}/contract" if portal else f"{LEADS}/{lead_id}/contract"


async def upload(
    client: AsyncClient,
    url: str,
    version: int,
    data: bytes = PDF,
    name: str = "signed.pdf",
    content_type: str = "application/pdf",
) -> Any:
    return await client.post(
        f"{url}/signed-copy",
        data={"version": str(version)},
        files={"file": (name, data, content_type)},
    )


async def fill(client: AsyncClient, url: str, **fields: Any) -> dict[str, Any]:
    """Saves the fields; in the portal, a tax ID also gets its card, as signing there needs it."""
    version = (await client.get(url)).json()["version"]
    r = await client.patch(url, json=fields | {"version": version})
    assert r.status_code == 200, r.text
    if url.startswith(PORTAL) and fields.get("tax_id"):
        r = await attach_card(client, url, r.json()["version"])
        assert r.status_code == 200, r.text
    return dict(r.json())


async def attach_card(
    client: AsyncClient, url: str, version: int, data: bytes = PNG, name: str = "npwp.png"
) -> Any:
    return await client.post(
        f"{url}/tax-id-file",
        data={"version": str(version)},
        files={"file": (name, data, "image/png" if name.endswith(".png") else "application/pdf")},
    )


async def test_exhibitor_fills_and_signs(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await portal_exhibitor(admin, edition)
    url = contract_url(lead_id)

    contract = (await portal.get(url)).json()
    assert (contract["status"], contract["booth_code"], contract["total_amount"]) == (
        "DRAFT",
        "A01",
        "15000000.00",
    )
    r = await upload(portal, url, contract["version"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CONTRACT_INCOMPLETE"
    assert set(r.json()["error"]["fields"]) == {
        "pic_name",
        "company_address",
        "tax_id_type",
        "tax_id",
        "tax_id_file",
    }

    contract = await fill(portal, url, **FIELDS | {"tax_id": " 01.234.567.8-901.000 "})
    assert contract["tax_id"] == "01.234.567.8-901.000"
    r = await portal.patch(url, json={"discount_amount": "1", "version": contract["version"]})
    assert r.status_code == 422  # the discount is staff only

    r = await upload(portal, url, contract["version"], name="C:\\scans\\kontrak final.pdf")
    assert r.status_code == 200, r.text
    signed = r.json()
    assert signed["status"] == "SIGNED"
    assert signed["signed_at"] is not None
    assert signed["signed_file_name"] == "kontrak final.pdf"
    [(bucket, key)] = [k for k in storage.objects if k[1].endswith(".pdf")]
    assert bucket == get_settings().s3_bucket_contracts
    assert key.endswith(".pdf") and "kontrak" not in key

    r = await portal.get(f"{url}/signed-copy")
    assert r.status_code == 200
    assert r.content == PDF
    assert r.headers["content-type"] == "application/pdf"
    assert f'filename="{edition.code}-C-0001-signed.pdf"' in r.headers["content-disposition"]

    me = (await portal.get(f"{PORTAL}/auth/me")).json()
    assert me["exhibitors"][0]["contract_status"] == "SIGNED"

    async with get_sessionmaker()() as session:
        actions = (
            await session.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "exhibitor_contract")
            )
        ).all()
        sign = await session.scalar(select(AuditLog).where(AuditLog.action == "sign"))
    assert set(actions) == {"create", "update", "attach_tax_id", "sign"}
    assert sign is not None and sign.source == "PORTAL"


async def test_signed_contract_is_read_only(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await portal_exhibitor(admin, edition)
    url = contract_url(lead_id)
    contract = await fill(portal, url, **FIELDS)
    signed = (await upload(portal, url, contract["version"])).json()

    r = await portal.patch(url, json={"pic_name": "Someone Else", "version": signed["version"]})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONTRACT_SIGNED"
    r = await upload(portal, url, signed["version"])
    assert r.json()["error"]["code"] == "CONTRACT_SIGNED"
    staff_url = contract_url(lead_id, portal=False)
    r = await admin.patch(staff_url, json={"discount_amount": "1", "version": signed["version"]})
    assert r.json()["error"]["code"] == "CONTRACT_SIGNED"
    assert len(storage.objects) == 2  # the signed PDF and the NPWP card


async def test_upload_checks(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await portal_exhibitor(admin, edition)
    url = contract_url(lead_id)
    version = (await fill(portal, url, **FIELDS))["version"]

    for kwargs in (
        {"name": "signed.docx"},
        {"content_type": "application/msword"},
        {"data": b"PK\x03\x04 not a pdf"},
        {"data": b""},
    ):
        r = await upload(portal, url, version, **kwargs)
        assert r.status_code == 422, kwargs
        assert "file" in r.json()["error"]["fields"]

    big = PDF + b"0" * get_settings().contract_file_max_bytes
    r = await upload(portal, url, version, data=big)
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"
    r = await upload(portal, url, version + 5)
    assert r.status_code == 409  # stale version
    r = await portal.post(
        f"{url}/signed-copy",
        data={"version": str(version)},
        files={"file": ("signed.pdf", PDF, "application/pdf")},
        headers={"X-CSRF-Token": "forged"},
    )
    assert r.status_code == 403
    assert all(not k.endswith(".pdf") for _, k in storage.objects)  # only the NPWP card
    assert (await portal.get(f"{url}/signed-copy")).status_code == 404


async def test_portal_sees_only_its_own_contract(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    mine, my_lead = await portal_exhibitor(admin, edition)
    theirs, their_lead = await portal_exhibitor(admin, edition, "booth-002@example.test", "A02")
    contract = await fill(theirs, contract_url(their_lead), **FIELDS)
    await upload(theirs, contract_url(their_lead), contract["version"])

    url = contract_url(their_lead)
    assert (await mine.get(url)).status_code == 404
    assert (await mine.patch(url, json={"pic_name": "x", "version": 1})).status_code == 404
    assert (await upload(mine, url, contract["version"])).status_code == 404
    assert (await mine.get(f"{url}/signed-copy")).status_code == 404
    assert (await mine.get(contract_url(my_lead))).status_code == 200

    # Staff session cannot use portal routes and the other way around.
    assert (await admin.get(url)).status_code == 401
    assert (await mine.get(contract_url(my_lead, portal=False))).status_code == 401


async def test_staff_discount_upload_and_download(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    url = contract_url(converted["lead"]["id"], portal=False)

    contract = await fill(admin, url, discount_amount="2500000")
    assert (contract["discount_amount"], contract["total_amount"]) == ("2500000.00", "12500000.00")
    r = await admin.patch(url, json={"discount_amount": "99999999", "version": contract["version"]})
    assert r.status_code == 422
    assert "discount_amount" in r.json()["error"]["fields"]

    # Exhibitor sent the signed copy by chat; sales uploads it.
    contract = await fill(admin, url, **FIELDS)
    r = await upload(admin, url, contract["version"])
    assert r.status_code == 200, r.text
    r = await admin.get(f"{url}/signed-copy")
    assert (r.status_code, r.content) == (200, PDF)

    async with get_sessionmaker()() as session:
        row = await session.scalar(select(ExhibitorContract))
    assert row is not None and row.total_amount == row.booth_price - row.discount_amount


async def test_staff_permissions(storage: MemoryStorage) -> None:
    edition = await make_edition()
    await sales_role()
    admin = await admin_for(edition)
    converted = await exhibitor(admin, edition)
    url = contract_url(converted["lead"]["id"], portal=False)

    _, owned = await actor(RoleGrant(SALES_ROLE, "OWNED", edition.id))
    assert (await owned.get(url)).status_code == 404  # not their lead
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    assert (await sales.get(url)).status_code == 200
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))
    assert (await agent.get(url)).status_code == 403
    assert (await agent.get(f"{url}/signed-copy")).status_code == 403


async def test_archived_edition_is_read_only(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await portal_exhibitor(admin, edition)
    url = contract_url(lead_id)
    version = (await portal.get(url)).json()["version"]
    async with get_sessionmaker()() as session, session.begin():
        row = await session.get(Edition, edition.id)
        assert row is not None
        row.status = EditionStatus.ARCHIVED
    r = await portal.patch(url, json=FIELDS | {"version": version})
    assert r.json()["error"]["code"] == "EDITION_ARCHIVED"
    assert (await portal.get(url)).status_code == 200


async def test_tax_id_npwp_or_ktp_with_card(storage: MemoryStorage) -> None:
    """No NPWP: the signer's KTP, and a photo of the card either way (owner request 2026-11-18)."""
    edition = await make_edition()
    admin = await admin_for(edition)
    portal, lead_id = await portal_exhibitor(admin, edition)
    url = contract_url(lead_id)
    contract = (await portal.get(url)).json()

    for kind, number, ok in (
        ("KTP", "3171 0123 4567 0001", True),
        ("KTP", "01.234.567.8-901.000", False),  # 15 digits
        ("NPWP", "01.234.567.8-901.000", True),
        ("NPWP", "0012 3456 7890 1234", True),  # the 16-digit NPWP
        ("NPWP", "NPWP-123", False),
        ("SIM", "123", False),
    ):
        r = await portal.patch(
            url, json={"tax_id_type": kind, "tax_id": number, "version": contract["version"]}
        )
        assert (r.status_code == 200) is ok, (kind, number, r.text)
        if ok:
            contract = r.json()
    assert (contract["tax_id_type"], contract["has_tax_id_file"]) == ("NPWP", False)

    contract = (
        await portal.patch(
            url,
            json={
                "pic_name": "Budi",
                "company_address": "Jl. Sudirman 1",
                "tax_id_type": "KTP",
                "tax_id": "3171012345670001",
                "version": contract["version"],
            },
        )
    ).json()
    r = await upload(portal, url, contract["version"])
    assert r.json()["error"]["fields"] == {"tax_id_file": "Required before signing."}

    r = await attach_card(portal, url, contract["version"], data=b"GIF89a", name="ktp.gif")
    assert r.status_code == 422
    r = await attach_card(portal, url, contract["version"], name="C:\\scan\\ktp budi.png")
    assert r.status_code == 200, r.text
    contract = r.json()
    assert (contract["has_tax_id_file"], contract["tax_id_file_name"]) == (True, "ktp budi.png")

    # Private: the exhibitor and staff download it; the name comes from the server.
    for client, card_url in ((portal, url), (admin, contract_url(lead_id, portal=False))):
        r = await client.get(f"{card_url}/tax-id-file")
        assert (r.status_code, r.content) == (200, PNG)
        assert f'filename="ktp-{lead_id}.png"' in r.headers["content-disposition"]

    r = await upload(portal, url, contract["version"])
    assert r.status_code == 200, r.text
    r = await attach_card(portal, url, r.json()["version"])
    assert r.json()["error"]["code"] == "CONTRACT_SIGNED"
