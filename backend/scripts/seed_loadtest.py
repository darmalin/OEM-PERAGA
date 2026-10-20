"""Seed a LOADTEST edition for load tests (dev/staging only, never production).

Creates exhibition LOADTEST, edition LOADTEST<year>, N leads, M registrations with active
QR credentials, one gate, and one active scanner device. The device token and the QR token
hashes are written to --out (JSON), never printed.

    python -m scripts.seed_loadtest --leads 50000 --registered 5000 --out /tmp/loadtest.json
"""

import argparse
import asyncio
import json
import random
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import insert, select

import app.models  # noqa: F401 - registers every model, so foreign keys resolve
from app.core.config import get_settings
from app.core.crypto import encrypt
from app.core.db import new_id, task_session
from app.modules.checkin.models import Gate, ScannerDevice
from app.modules.checkin.rules import new_device_secret
from app.modules.exhibitions.models import Edition, EditionCounter, Exhibition
from app.modules.registrations.models import QrCredential, VisitorRegistration
from app.modules.registrations.rules import new_qr_token
from app.modules.visitors.models import VisitorLead

COUNTRIES = ["VN", "ID", "MY", "TH", "SG", "PH", None]
SOURCES = ["EXCEL", "MANUAL", "WEBSITE", "API", "TELEMARKETING"]
BATCH = 2000


async def seed(leads: int, registered: int, year: int) -> dict[str, Any]:
    if get_settings().environment == "production":
        raise SystemExit("refusing to seed load-test data in production")
    code = f"LOADTEST{year}"
    async with task_session() as session, session.begin():
        if await session.scalar(select(Edition.id).where(Edition.code == code)):
            raise SystemExit(f"{code} already exists; pass another --year")
        ex = await session.scalar(select(Exhibition).where(Exhibition.code == "LOADTEST"))
        if ex is None:
            ex = Exhibition(code="LOADTEST", name="Load test")
            session.add(ex)
            await session.flush()
        edition = Edition(
            exhibition_id=ex.id, year=year, code=code, name=f"Load test {year}",
            start_date=date(year, 3, 10), end_date=date(year, 3, 12),
            timezone="Asia/Jakarta", default_currency="IDR",
            registration_id_prefix=code, status="ACTIVE",
        )  # fmt: skip
        session.add(edition)
        await session.flush()
        session.add(EditionCounter(edition_id=edition.id, last_value=leads))

        rng = random.Random(42)
        lead_ids = []
        for start in range(0, leads, BATCH):
            rows = []
            for n in range(start, min(start + BATCH, leads)):
                lead_id = new_id()
                lead_ids.append(lead_id)
                email = f"load-{n:06d}@example.test"
                rows.append(
                    {
                        "id": lead_id, "edition_id": edition.id,
                        "registration_code": f"{code}{n + 1:06d}",
                        "first_name": f"Load Visitor {n:06d}", "email": email,
                        "email_normalized": email, "phone_normalized": f"+8490{n:07d}",
                        "country": rng.choice(COUNTRIES), "source": rng.choice(SOURCES),
                        "company_name": f"Company {n % 997}", "custom_fields": {},
                        "product_categories": [],
                        "registration_status": "REGISTERED" if n < registered else "NOT_REGISTERED",
                        "qr_status": "ACTIVE" if n < registered else "NONE",
                    }
                )  # fmt: skip
            await session.execute(insert(VisitorLead), rows)

        hashes = []
        for start in range(0, registered, BATCH):
            regs, creds = [], []
            for lead_id in lead_ids[start : min(start + BATCH, registered)]:
                reg_id = new_id()
                token, token_hash = new_qr_token()
                hashes.append(token_hash)
                regs.append({"id": reg_id, "edition_id": edition.id, "visitor_lead_id": lead_id,
                             "channel": "IMPORT", "status": "REGISTERED"})  # fmt: skip
                creds.append({"id": new_id(), "edition_id": edition.id, "registration_id": reg_id,
                              "token_hash": token_hash, "token_enc": encrypt(token),
                              "status": "ACTIVE"})  # fmt: skip
            await session.execute(insert(VisitorRegistration), regs)
            await session.execute(insert(QrCredential), creds)

        gate = Gate(edition_id=edition.id, code="LOAD", name="Load test gate")
        session.add(gate)
        await session.flush()
        secret, secret_hash = new_device_secret()
        device = ScannerDevice(
            edition_id=edition.id, gate_id=gate.id, name="Load test device", status="ACTIVE",
            secret_hash=secret_hash, activated_at=datetime.now(UTC),
        )  # fmt: skip
        session.add(device)
        await session.flush()

    return {
        "edition_id": str(edition.id),
        "edition_code": code,
        "device_token": f"{device.id}.{secret}",
        "token_hashes": hashes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leads", type=int, default=50_000)
    parser.add_argument("--registered", type=int, default=5_000)
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year + 1)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    data = asyncio.run(seed(args.leads, min(args.registered, args.leads), args.year))
    with open(args.out, "w") as f:
        json.dump(data, f)
    print(f"seeded {data['edition_code']}: {args.leads} leads -> {args.out}")


if __name__ == "__main__":
    main()
