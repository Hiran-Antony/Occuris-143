"""
Module 5 — Fixture Scenario Builder (§10)
Seeded generator producing a forensically realistic synthetic AIS dataset
with 8 distinct maritime scenarios and ground-truth validation manifest.

Scenarios embedded:
- V001: Normal commercial transit (on-time, continuous AIS) -> NORMAL_TRANSIT
- V002: Transit delayed by high wind conditions -> EXPLAINED_DELAY (WEATHER)
- V003: Unexplained delay with a 38-minute AIS blackout -> POTENTIAL_UNEXPLAINED_DELAY (AIS_GAP)
- V004 + V005: Coordinated dark vessel pair with meeting at sea (< 500m separation, SOG < 3 kn) -> RENDEZVOUS & COORDINATED_DARK
- V004: Post-gap trajectory re-identifiable via Behavioral DNA matching
- V006: Legitimate stop at anchorage (nav_status=1 'At anchor') -> EXPLAINED_DELAY (NAV_STATUS)
- V007: Transit experiencing regional traffic congestion -> EXPLAINED_DELAY (TRAFFIC)
- V008: Ongoing transit inside monitored sector without exit -> IN_REGION
"""

from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = ROOT / "data" / "raw" / "synthetic"
DEFAULT_CSV = OUTPUT_DIR / "module5_demo.csv"
DEFAULT_JSON = OUTPUT_DIR / "ground_truth.json"


def generate_fixture_dataset(
    seed: int = 42,
    csv_path: Optional[Path] = None,
    json_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Generate 8 deterministic synthetic maritime scenarios with complete ground truth.
    """
    random.seed(seed)
    target_csv = csv_path or DEFAULT_CSV
    target_json = json_path or DEFAULT_JSON
    target_csv.parent.mkdir(parents=True, exist_ok=True)

    base_time = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    all_rows: List[Dict[str, Any]] = []

    # ── 1. V001: Normal Commercial Trader (steady southward passage) ──────────
    t = base_time
    lat, lon = 19.50, 65.50
    for step in range(60):
        all_rows.append({
            "mmsi": 477001001,
            "vessel_id": "V001",
            "vessel_name": "NORMAL TRADER",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": round(13.5 + 0.3 * math.sin(step), 1),
            "cog": 183.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        lat -= 0.052
        lon -= 0.005

    # ── 2. V002: Weather-Delayed Tanker (wind overlap) ────────────────────────
    t = base_time
    lat, lon = 17.20, 67.50
    for step in range(65):
        sog = 12.0 if step < 20 else 6.2
        all_rows.append({
            "mmsi": 477002002,
            "vessel_id": "V002",
            "vessel_name": "WIND DELAYED TANKER",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": sog,
            "cog": 268.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        lon -= 0.045 if step < 20 else 0.022
        lat -= 0.002

    # ── 3. V003: Unexplained Delay with 38-minute AIS Blackout ────────────────
    t = base_time
    lat, lon = 15.20, 61.80
    for step in range(50):
        if step == 20:
            t += timedelta(minutes=38)
        all_rows.append({
            "mmsi": 477003003,
            "vessel_id": "V003",
            "vessel_name": "BLACKOUT CARGO",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": round(11.0 if step < 20 else 8.2, 1),
            "cog": 92.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        lon += 0.038
        lat += 0.001

    # ── 4 & 5. V004 & V005: Coordinated Dark Vessels + Mid-Sea Rendezvous ─────
    t = base_time
    lat4, lon4 = 16.80, 64.20
    lat5, lon5 = 16.20, 64.80

    for step in range(60):
        if step < 30:
            lat4 -= 0.01
            lon4 += 0.01
            lat5 += 0.01
            lon5 -= 0.01

        is_rdvz = 37 <= step <= 39
        skip_gap = (step == 42)

        if skip_gap:
            t += timedelta(minutes=25)

        if is_rdvz:
            sog4, sog5 = 1.2, 1.4
            lat4_cur, lon4_cur = 16.500, 64.500
            lat5_cur, lon5_cur = 16.502, 64.502
        elif step > 39:
            sog4 = 12.0 + 0.3 * math.cos(step)
            sog5 = 12.0 + 0.3 * math.sin(step)
            offset = (step - 39) * 0.008
            lat4_cur, lon4_cur = 16.500 - offset, 64.500 + offset
            lat5_cur, lon5_cur = 16.502 - offset, 64.502 + offset
        else:
            sog4 = 14.2 + 0.5 * math.cos(step)
            sog5 = 10.0 + 0.4 * math.sin(step)
            lat4_cur, lon4_cur = lat4, lon4
            lat5_cur, lon5_cur = lat5, lon5

        all_rows.append({
            "mmsi": 477004004,
            "vessel_id": "V004",
            "vessel_name": "RENDEZVOUS LEAD",
            "timestamp": t.isoformat(),
            "lat": round(lat4_cur, 5),
            "lon": round(lon4_cur, 5),
            "sog": round(sog4, 1),
            "cog": 135.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })

        all_rows.append({
            "mmsi": 477005005,
            "vessel_id": "V005",
            "vessel_name": "RENDEZVOUS TENDER",
            "timestamp": t.isoformat(),
            "lat": round(lat5_cur, 5),
            "lon": round(lon5_cur, 5),
            "sog": round(sog5, 1),
            "cog": 315.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)

    # ── 6. V006: Legitimate Stop at Anchorage (nav_status=1) ─────────────────
    t = base_time
    lat, lon = 18.80, 71.50
    for step in range(50):
        # Enters anchorage and drops anchor between steps 15 and 35 (3.3 hours)
        is_anchored = 15 <= step <= 35
        nav_status = 1 if is_anchored else 0
        sog = 0.2 if is_anchored else 11.5
        all_rows.append({
            "mmsi": 477006006,
            "vessel_id": "V006",
            "vessel_name": "ANCHORED BULKER",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": sog,
            "cog": 180.0,
            "nav_status": nav_status,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        if not is_anchored:
            lat -= 0.035

    # ── 7. V007: Corridor Traffic Congestion Transit ──────────────────────────
    t = base_time
    lat, lon = 16.10, 68.20
    for step in range(45):
        all_rows.append({
            "mmsi": 477007007,
            "vessel_id": "V007",
            "vessel_name": "CONGESTED FEEDER",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": round(9.0 + 0.2 * math.sin(step), 1),
            "cog": 90.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        lon += 0.03

    # ── 8. V008: Vessel Entering Sector but Not Exited (IN_REGION) ────────────
    t = base_time + timedelta(hours=4)
    lat, lon = 20.00, 66.00
    for step in range(25):  # Ends while vessel still deep inside sector
        all_rows.append({
            "mmsi": 477008008,
            "vessel_id": "V008",
            "vessel_name": "INBOUND CONTAINER",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": 15.0,
            "cog": 180.0,
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        lat -= 0.04

    # Sort all rows by (vessel_id, timestamp)
    all_rows.sort(key=lambda r: (r["vessel_id"], r["timestamp"]))

    with open(target_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "mmsi", "vessel_id", "vessel_name", "timestamp",
            "lat", "lon", "sog", "cog", "nav_status", "source"
        ])
        writer.writeheader()
        writer.writerows(all_rows)

    ground_truth = {
        "dataset": target_csv.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "_isolation_guard": "GROUND_TRUTH_FOR_TESTS_ONLY",
        "scenarios_count": 8,
        "cases": {
            "V001": {
                "expected_classification": "NORMAL_TRANSIT",
                "has_ais_gap": False,
                "has_unexplained_delay": False,
            },
            "V002": {
                "expected_classification": "EXPLAINED_DELAY",
                "primary_explanation": "WEATHER",
                "has_ais_gap": False,
            },
            "V003": {
                "expected_classification": "POTENTIAL_UNEXPLAINED_DELAY",
                "has_ais_gap": True,
                "gap_duration_minutes": 38.0,
            },
            "V004": {
                "re_identifiable_via_dna": True,
                "collective_anomalies": ["COORDINATED_DARK", "RENDEZVOUS"],
                "partner_vessel": "V005",
            },
            "V005": {
                "collective_anomalies": ["COORDINATED_DARK", "RENDEZVOUS"],
                "partner_vessel": "V004",
            },
            "V006": {
                "expected_classification": "EXPLAINED_DELAY",
                "primary_explanation": "NAV_STATUS",
                "has_ais_gap": False,
            },
            "V007": {
                "expected_classification": "NORMAL_OR_EXPLAINED",
                "has_ais_gap": False,
            },
            "V008": {
                "expected_status": "IN_REGION",
                "has_ais_gap": False,
            },
        },
    }

    with open(target_json, mode="w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


if __name__ == "__main__":
    generate_fixture_dataset()
