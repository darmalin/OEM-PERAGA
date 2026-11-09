"""Order form setup API (Phase 2 of docs/EXHIBITOR_ORDER_FORMS.md)."""

import io
from typing import Any

from httpx import AsyncClient
from openpyxl import Workbook

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.storage import MemoryStorage
from app.modules.exhibitions.models import Edition, EditionStatus
from tests.factories import RoleGrant, actor, make_edition
from tests.test_exhibitor_leads import SALES_ROLE, admin_for, sales_role

URL = "/api/v1/order-forms"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def add_form(client: AsyncClient, edition: Edition, code: str = "04", **kw: Any) -> Any:
    body = {"edition_id": str(edition.id), "code": code, "title": "Electrical", **kw}
    return await client.post(URL, json=body)


async def add_item(
    client: AsyncClient, form: dict[str, Any], code: str = "E-001", **kw: Any
) -> Any:
    body = {"code": code, "name": "Fluorescent lamp", "price_regular": "740600", **kw}
    return await client.post(f"{URL}/{form['id']}/items", json=body)


async def catalog_form(client: AsyncClient, edition: Edition, code: str = "04") -> dict[str, Any]:
    r = await add_form(client, edition, code, has_catalog=True)
    assert r.status_code == 201, r.text
    return dict(r.json())


async def items(client: AsyncClient, form: dict[str, Any], **params: Any) -> list[dict[str, Any]]:
    r = await client.get(f"{URL}/{form['id']}/items", params=params)
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


def workbook(rows: list[list[Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def upload_catalog(client: AsyncClient, form: dict[str, Any], data: bytes) -> Any:
    files = {"file": ("catalog.xlsx", data, XLSX)}
    return await client.post(f"{URL}/{form['id']}/items/import", files=files)


HEADER = ["Section", "Code", "Name", "Size", "Price Regular", "Price Surcharge", "Active"]


# --- forms -------------------------------------------------------------------------------


async def test_create_form_with_defaults() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    r = await add_form(admin, edition, " 02a ", title=" Social Media Promotion ")
    assert r.status_code == 201, r.text
    form = r.json()
    assert form["code"] == "02a"
    assert form["title"] == "Social Media Promotion"
    assert form["currency"] == "IDR"  # edition default
    assert form["is_published"] is False
    assert form["has_catalog"] is False
    assert form["attachment_purposes"] == []
    assert form["active_item_count"] == 0

    r = await add_form(admin, edition, "02a")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_FORM_CODE"
    assert (await add_form(admin, edition, "2a")).status_code == 422
    assert (await add_form(admin, edition, "05", details_type="survey")).status_code == 422


async def test_form_field_rules() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    cases = [
        ({"allow_custom_items": True}, "allow_custom_items"),
        ({"deadline_on": "2027-02-10", "closes_on": "2027-02-09"}, "closes_on"),
        ({"secondary_deadline_label": "Material Deadline"}, "secondary_deadline_on"),
        ({"secondary_deadline_on": "2027-02-10"}, "secondary_deadline_label"),
    ]
    for kw, field in cases:
        r = await add_form(admin, edition, **kw)
        assert r.status_code == 422, kw
        assert field in r.json()["error"]["fields"], r.text
    r = await add_form(
        admin,
        edition,
        attachment_purposes=["LOGO", "LOGO", "PRODUCT_IMAGE"],
        secondary_deadline_label="Material Deadline",
        secondary_deadline_on="2027-02-15",
    )
    assert r.status_code == 201, r.text
    assert r.json()["attachment_purposes"] == ["LOGO", "PRODUCT_IMAGE"]


async def test_publish_needs_something_to_fill() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    url = f"{URL}/{form['id']}"
    r = await admin.patch(url, json={"is_published": True, "version": form["version"]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "FORM_EMPTY"

    item = (await add_item(admin, form)).json()
    r = await admin.patch(url, json={"is_published": True, "version": form["version"]})
    assert r.status_code == 200, r.text
    assert r.json()["active_item_count"] == 1

    # Deactivating the only item of a published catalog form is refused and rolled back.
    r = await admin.patch(
        f"{url}/items/{item['id']}", json={"is_active": False, "version": item["version"]}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "FORM_EMPTY"
    assert [i["is_active"] for i in await items(admin, form)] == [True]

    # A details form needs no catalog.
    r = await add_form(admin, edition, "01", details_type="directory_listing", is_published=True)
    assert r.status_code == 201, r.text


async def test_update_form_and_version() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = (await add_form(admin, edition)).json()
    url = f"{URL}/{form['id']}"
    r = await admin.patch(
        url,
        json={"title": "Electrical Fittings", "deadline_on": "2027-02-23", "version": 1},
    )
    assert r.status_code == 200, r.text
    assert r.json()["deadline_on"] == "2027-02-23"
    assert r.json()["version"] == 2
    assert (await admin.patch(url, json={"title": "Again", "version": 1})).status_code == 409
    r = await admin.patch(url, json={"code": "05", "version": 2})
    assert r.status_code == 422  # the number is fixed
    r = await admin.patch(url, json={"title": "", "version": 2})
    assert r.status_code == 422
    assert (await admin.get(url)).json()["title"] == "Electrical Fittings"


async def test_archived_edition_is_read_only() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    async with get_sessionmaker()() as session, session.begin():
        row = await session.get(Edition, edition.id)
        assert row is not None
        row.status = EditionStatus.ARCHIVED
    r = await add_item(admin, form)
    assert r.json()["error"]["code"] == "EDITION_ARCHIVED"
    assert (await admin.get(f"{URL}/{form['id']}")).status_code == 200


# --- access ------------------------------------------------------------------------------


async def test_access() -> None:
    edition, other = await make_edition(), await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    await add_item(admin, form)

    # Exhibitor sales can read forms next to their leads but cannot set them up.
    await sales_role()
    _, sales = await actor(RoleGrant(SALES_ROLE, "EDITION", edition.id))
    r = await sales.get(URL, params={"edition_id": str(edition.id)})
    assert r.status_code == 200, r.text
    assert len(await items(sales, form)) == 1
    assert (await add_form(sales, edition, "05")).status_code == 403
    assert (await add_item(sales, form, "E-002")).status_code == 403

    # Edition-wide access only: an own-leads grant cannot set up forms.
    _, owned = await actor(RoleGrant("EXHIBITION_ADMIN", "OWNED", edition.id))
    assert (await add_form(owned, edition, "05")).status_code == 403

    # Another edition's admin does not see the form; no exhibitor permission at all is 403.
    other_admin = await admin_for(other)
    assert (await other_admin.get(f"{URL}/{form['id']}")).status_code == 404
    r = await other_admin.get(URL, params={"edition_id": str(edition.id)})
    assert r.status_code == 404
    _, agent = await actor(RoleGrant("TELEMARKETING_AGENT", "EDITION", edition.id))
    assert (await agent.get(URL, params={"edition_id": str(edition.id)})).status_code == 403


# --- items -------------------------------------------------------------------------------


async def test_items() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    r = await add_item(
        admin, form, " E-001 ", section="A. Lighting", size="40 W", price_surcharge="814660"
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert (item["code"], item["price_regular"], item["price_surcharge"]) == (
        "E-001",
        "740600.00",
        "814660.00",
    )
    assert item["price_onsite"] is None
    assert item["has_image"] is False

    r = await add_item(admin, form, "E-001")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE_ITEM_CODE"
    assert (await add_item(admin, form, "E-002", price_regular="-1")).status_code == 422
    assert (await add_item(admin, form, "E-003", max_quantity=0)).status_code == 422

    second = (await add_item(admin, form, "E-002", sort_order=1)).json()
    r = await admin.patch(
        f"{URL}/{form['id']}/items/{second['id']}",
        json={"is_active": False, "version": second["version"]},
    )
    assert r.status_code == 200, r.text
    assert [i["code"] for i in await items(admin, form)] == ["E-001"]
    assert [i["code"] for i in await items(admin, form, include_inactive=True)] == [
        "E-001",
        "E-002",
    ]

    # An item is reached only through its own form.
    other = await catalog_form(admin, edition, "07")
    r = await admin.patch(f"{URL}/{other['id']}/items/{item['id']}", json={"version": 1})
    assert r.status_code == 404


async def test_item_image(storage: MemoryStorage) -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    item = (await add_item(admin, form)).json()
    url = f"{URL}/{form['id']}/items/{item['id']}/image"
    assert (await admin.get(url)).status_code == 404

    r = await admin.post(
        url, files={"file": ("lamp.png", PNG, "image/png")}, data={"version": str(item["version"])}
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_image"] is True
    r = await admin.get(url)
    assert r.status_code == 200
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["content-disposition"].startswith("inline")
    assert any(b == get_settings().s3_bucket_orders for b, _key in storage.objects)

    version = str(item["version"] + 1)
    for name, data, mime in [
        ("lamp.gif", b"GIF89a", "image/gif"),
        ("lamp.png", b"not an image", "image/png"),
        ("lamp.jpg", PNG, "image/jpeg"),
    ]:
        r = await admin.post(url, files={"file": (name, data, mime)}, data={"version": version})
        assert r.status_code == 422, name


# --- copy --------------------------------------------------------------------------------


async def test_copy_forms_from_another_edition() -> None:
    source = await make_edition(exhibition_code="CPY", year=2026)
    target = await make_edition(exhibition_code="CPY", year=2027)
    _, admin = await actor(
        RoleGrant("EXHIBITION_ADMIN", "EDITION", source.id),
        RoleGrant("EXHIBITION_ADMIN", "EDITION", target.id),
    )
    form = await catalog_form(admin, source)
    await add_item(admin, form, "E-001")
    await add_item(admin, form, "E-002")
    r = await admin.patch(
        f"{URL}/{form['id']}",
        json={"deadline_on": "2026-02-23", "is_published": True, "version": form["version"]},
    )
    assert r.status_code == 200, r.text
    await add_form(admin, source, "01", details_type="directory_listing")
    await add_form(admin, target, "01", title="Kept as it is")

    body = {"from_edition_id": str(source.id), "to_edition_id": str(target.id)}
    r = await admin.post(f"{URL}/copy", json=body)
    assert r.status_code == 200, r.text
    assert r.json() == {"forms_copied": 1, "items_copied": 2, "skipped_codes": ["01"]}

    copied = (await admin.get(URL, params={"edition_id": str(target.id)})).json()["items"]
    by_code = {f["code"]: f for f in copied}
    assert by_code["01"]["title"] == "Kept as it is"
    assert by_code["04"]["deadline_on"] is None
    assert by_code["04"]["is_published"] is False
    assert by_code["04"]["active_item_count"] == 2

    # Copying again changes nothing; copying needs setup rights in both editions.
    r = await admin.post(f"{URL}/copy", json=body)
    assert r.json()["forms_copied"] == 0
    target_only = await admin_for(target)
    assert (await target_only.post(f"{URL}/copy", json=body)).status_code == 404
    body["from_edition_id"] = body["to_edition_id"]
    assert (await admin.post(f"{URL}/copy", json=body)).status_code == 422


# --- import ------------------------------------------------------------------------------


async def test_import_creates_and_updates_by_code() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    await add_item(admin, form, "E-001", price_surcharge="800000")

    data = workbook(
        [
            HEADER,
            ["A. Lighting", "e-001", "Fluorescent lamp 40 W", "40 W", 750000, None, "yes"],
            ["A. Lighting", "E-002", "Spotlight", None, "1,046,500", 1100000, None],
            [None, None, None, None, None, None, None],  # blank rows are skipped
            ["B. Power", "P-001", "Power 2 A", None, 1014300.0, None, "no"],
        ]
    )
    r = await upload_catalog(admin, form, data)
    assert r.status_code == 200, r.text
    assert r.json() == {"created": 2, "updated": 1, "errors": []}
    by_code = {i["code"]: i for i in await items(admin, form, include_inactive=True)}
    assert by_code["E-001"]["price_regular"] == "750000.00"
    assert by_code["E-001"]["price_surcharge"] is None  # a blank cell clears it
    assert by_code["E-002"]["price_regular"] == "1046500.00"
    assert by_code["P-001"]["is_active"] is False

    # The same sheet again changes nothing.
    r = await upload_catalog(admin, form, data)
    assert r.json() == {"created": 0, "updated": 0, "errors": []}


async def test_import_is_all_or_nothing() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    data = workbook(
        [
            HEADER,
            ["A", "E-001", "Lamp", None, 100, None, None],
            ["A", "E-002", None, None, 100, None, None],
            ["A", "E-003", "Lamp", None, "abc", None, None],
            ["A", "e-001", "Lamp again", None, 100, None, None],
        ]
    )
    r = await upload_catalog(admin, form, data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["created"], body["updated"]) == (0, 0)
    assert [(e["row"], sorted(e["errors"])) for e in body["errors"]] == [
        (3, ["name"]),
        (4, ["price_regular"]),
        (5, ["code"]),
    ]
    assert await items(admin, form) == []


async def test_import_rejects_bad_files() -> None:
    edition = await make_edition()
    admin = await admin_for(edition)
    form = await catalog_form(admin, edition)
    r = await upload_catalog(admin, form, b"Code,Name\nE-001,Lamp\n")
    assert r.status_code == 422
    r = await upload_catalog(admin, form, workbook([["Code", "Description"], ["E-001", "x"]]))
    assert r.status_code == 422
    assert "Name" in r.json()["error"]["fields"]["file"]

    r = await admin.get(f"{URL}/item-import-template")
    assert r.status_code == 200
    assert r.headers["content-type"] == XLSX
    r = await upload_catalog(admin, form, r.content)  # the template's example row imports
    assert r.json()["created"] == 1
