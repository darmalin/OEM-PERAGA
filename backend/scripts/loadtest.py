"""Load test for the two hot paths in spec 16: lead list/filter and the gate scan API.

    EMS_LOADTEST_PASSWORD=... python -m scripts.loadtest --base-url http://nginx \\
        --email admin@example.test --seed-file /tmp/loadtest.json --duration 30 --concurrency 20

Reports throughput, error rate, and latency percentiles per scenario. Targets must come
from the expected volume (leads, scanners, concurrent users); this tool only measures.
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class Stats:
    latencies_ms: list[float] = field(default_factory=list)
    statuses: Counter[int] = field(default_factory=Counter)

    def add(self, started: float, status: int) -> None:
        self.latencies_ms.append((time.perf_counter() - started) * 1000)
        self.statuses[status] += 1

    def report(self, name: str, seconds: float) -> dict[str, Any]:
        lat = sorted(self.latencies_ms)
        n = len(lat)
        errors = sum(c for s, c in self.statuses.items() if s >= 500 or s == 0)

        def pct(p: float) -> float:
            return round(lat[min(n - 1, int(p * n))], 1) if n else 0.0

        return {
            "scenario": name,
            "requests": n,
            "rps": round(n / seconds, 1),
            "errors_5xx": errors,
            "statuses": dict(self.statuses),
            "p50_ms": pct(0.50),
            "p95_ms": pct(0.95),
            "p99_ms": pct(0.99),
            "max_ms": round(lat[-1], 1) if n else 0.0,
            "mean_ms": round(statistics.fmean(lat), 1) if n else 0.0,
        }


def lead_query(edition_id: str, rng: random.Random) -> dict[str, Any]:
    params: dict[str, Any] = {
        "edition_id": edition_id,
        "page": rng.randint(1, 50),
        "page_size": 20,
    }
    match rng.randrange(6):
        case 0:
            params["source"] = rng.choice(["EXCEL", "MANUAL", "WEBSITE"])
        case 1:
            params["country"] = rng.choice(["VN", "ID", "MY"])
        case 2:
            params["q"] = f"Load Visitor {rng.randint(0, 499):03d}"
            params["page"] = 1
        case 3:
            params["telemarketing_status"] = "NEW"
            params["sort"] = "-lead_date"
        case 4:
            params["registration_status"] = "REGISTERED"
        case _:
            pass
    return params


async def run_leads(
    client: httpx.AsyncClient, edition_id: str, until: float, stats: Stats, seed: int
) -> None:
    rng = random.Random(seed)
    while time.perf_counter() < until:
        started = time.perf_counter()
        try:
            r = await client.get("/api/v1/visitor-leads", params=lead_query(edition_id, rng))
            stats.add(started, r.status_code)
        except httpx.HTTPError:
            stats.add(started, 0)


async def run_scans(
    client: httpx.AsyncClient, hashes: list[str], until: float, stats: Stats, seed: int
) -> None:
    rng = random.Random(seed)
    while time.perf_counter() < until:
        # ~5% unknown codes, like damaged or foreign QR codes at a real gate.
        token_hash = rng.choice(hashes) if rng.random() > 0.05 else f"{rng.getrandbits(256):064x}"
        started = time.perf_counter()
        try:
            r = await client.post(
                "/api/v1/gate/device/scans",
                json={"scan_event_id": str(uuid.uuid4()), "token_hash": token_hash},
            )
            stats.add(started, r.status_code)
        except httpx.HTTPError:
            stats.add(started, 0)


async def main(args: argparse.Namespace, seed: dict[str, Any]) -> None:
    limits = httpx.Limits(max_connections=args.concurrency * 2)
    results = []

    if args.scenario in ("leads", "all"):
        async with httpx.AsyncClient(base_url=args.base_url, limits=limits, timeout=30) as client:
            r = await client.post(
                "/api/v1/auth/login",
                json={"email": args.email, "password": os.environ["EMS_LOADTEST_PASSWORD"]},
            )
            r.raise_for_status()
            stats = Stats()
            start = time.perf_counter()
            until = start + args.duration
            await asyncio.gather(
                *(
                    run_leads(client, seed["edition_id"], until, stats, i)
                    for i in range(args.concurrency)
                )
            )
            results.append(stats.report("lead list/filter", time.perf_counter() - start))

    if args.scenario in ("scans", "all"):
        headers = {"X-Device-Token": seed["device_token"]}
        async with httpx.AsyncClient(
            base_url=args.base_url, limits=limits, timeout=30, headers=headers
        ) as client:
            stats = Stats()
            start = time.perf_counter()
            until = start + args.duration
            await asyncio.gather(
                *(
                    run_scans(client, seed["token_hashes"], until, stats, i)
                    for i in range(args.concurrency)
                )
            )
            results.append(stats.report("gate scan (online)", time.perf_counter() - start))

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://nginx")
    parser.add_argument("--email", required=True)
    parser.add_argument("--seed-file", required=True)
    parser.add_argument("--duration", type=float, default=30)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--scenario", choices=["leads", "scans", "all"], default="all")
    cli = parser.parse_args()
    with open(cli.seed_file) as f:
        asyncio.run(main(cli, json.load(f)))
