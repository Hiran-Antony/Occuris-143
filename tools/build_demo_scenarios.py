"""
Module 5 — Demo Scenario Builder (§10)
Generates a forensically realistic synthetic AIS dataset (data/raw/synthetic/module5_demo.csv)
and companion ground-truth manifest (data/raw/synthetic/ground_truth.json).

Scenarios embedded:
- V001: Normal commercial transit (on-time, continuous AIS) -> NORMAL_TRANSIT
- V002: Transit delayed by high wind conditions -> EXPLAINED_DELAY (WEATHER)
- V003: Unexplained delay with a 38-minute AIS blackout -> POTENTIAL_UNEXPLAINED_DELAY (AIS_GAP)
- V004 + V005: Coordinated dark vessel pair with meeting at sea (< 500m separation, SOG < 3 kn) -> RENDEZVOUS & COORDINATED_DARK
- V004: Post-gap trajectory re-identifiable via Behavioral DNA matching
"""

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "raw" / "synthetic"
CSV_PATH = OUTPUT_DIR / "module5_demo.csv"
GROUND_TRUTH_PATH = OUTPUT_DIR / "ground_truth.json"


def generate_demo_dataset():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    base_time = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    all_rows = []

    # ── 1. V001: Normal Commercial Trader (steady southward passage) ──────────
    # Starts at 19.5N, 65.5E, enters GATE_B (lat 18.0N), ends at 16.4N, 65.2E
    # Speed: ~13.5 kn, Course: ~183 deg
    t = base_time
    lat = 19.50
    lon = 65.50
    for step in range(60):  # 60 pings every 10 min = 10 hours
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
        lat -= 0.052  # approx 13.5 kn south
        lon -= 0.005

    # ── 2. V002: Weather-Delayed Tanker (wind overlap) ────────────────────────
    # Starts east at 17.2N, 67.5E, enters GATE_D (lon 66.0E)
    # Slows down significantly in western sector where wind > 6.5 m/s
    t = base_time
    lat = 17.20
    lon = 67.50
    for step in range(65):
        sog = 12.0 if step < 20 else 6.2  # Severe speed reduction due to adverse weather
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
    # Crosses GATE_A (lon 63.0E) heading east
    # Blackout between 03:20 and 04:00 UTC (38 min)
    t = base_time
    lat = 15.20
    lon = 61.80
    for step in range(50):
        # Introduce deliberate 38-min gap at step 20 (03:20 UTC)
        if step == 20:
            t += timedelta(minutes=38)

        all_rows.append({
            "mmsi": 477003003,
            "vessel_id": "V003",
            "vessel_name": "SUSPECT UNEXPLAINED",
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
    # Approach mutual location around 16.5N, 64.5E
    # Rendezvous: separation < 400m, both SOG < 2.0 kn for 25 min (from 06:10 to 06:35 UTC)
    # Coordinated Dark: both drop AIS from 07:00 to 07:25 UTC (25 min overlap within 2 NM)
    t = base_time
    lat4, lon4 = 16.80, 64.20
    lat5, lon5 = 16.20, 64.80

    for step in range(60):
        # Approach mutual location up to step 30
        if step < 30:
            lat4 -= 0.01
            lon4 += 0.01
            lat5 += 0.01
            lon5 -= 0.01

        # Rendezvous interval: steps 37 to 39 (06:10 to 06:30 UTC)
        is_rdvz = 37 <= step <= 39
        # Coordinated dark blackout: step 42 (07:00 to 07:25 UTC) -> 25 min gap
        skip_gap = (step == 42)

        if skip_gap:
            t += timedelta(minutes=25)

        if is_rdvz:
            # Mutual close proximity: 350m apart (0.003 deg), SOG 1.2 kn
            sog4, sog5 = 1.2, 1.4
            lat4_cur, lon4_cur = 16.500, 64.500
            lat5_cur, lon5_cur = 16.502, 64.502  # ~300m away
        elif step > 39:
            # After rendezvous, continue together in close proximity (< 1 NM)
            sog4 = 12.0 + 0.3 * math.cos(step)
            sog5 = 12.0 + 0.3 * math.sin(step)
            offset = (step - 39) * 0.008
            lat4_cur, lon4_cur = 16.500 - offset, 64.500 + offset
            lat5_cur, lon5_cur = 16.502 - offset, 64.502 + offset  # ~300m apart
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

    # Sort all rows by (vessel_id, timestamp)
    all_rows.sort(key=lambda r: (r["vessel_id"], r["timestamp"]))

    # Write CSV
    with open(CSV_PATH, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "mmsi", "vessel_id", "vessel_name", "timestamp",
            "lat", "lon", "sog", "cog", "nav_status", "source"
        ])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"[Demo Builder] Wrote {len(all_rows)} synthetic AIS pings to {CSV_PATH}")

    # Write Ground Truth
    ground_truth = {
        "dataset": "module5_demo.csv",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # ── GROUND TRUTH ISOLATION GUARD ──
        # This ground truth is consumed ONLY by test fixtures.
        # It MUST NOT be imported or read by production code in src/.
        "_isolation_guard": "GROUND_TRUTH_FOR_TESTS_ONLY",
        "cases": {
            "V001": {
                "expected_classification": "NORMAL_TRANSIT",
                "has_ais_gap": False,
                "has_unexplained_delay": False,
                # Module 6 expected states
                "m6_ais_state": "NORMAL",
                "m6_has_kinematic_episodes": False,
                "m6_reachability": "REACHABLE",
            },
            "V002": {
                "expected_classification": "EXPLAINED_DELAY",
                "primary_explanation": "WEATHER",
                "has_ais_gap": False,
                # Module 6 expected states
                "m6_ais_state": "NORMAL",
                "m6_has_kinematic_episodes": False,
                "m6_reachability": "REACHABLE",
            },
            "V003": {
                "expected_classification": "POTENTIAL_UNEXPLAINED_DELAY",
                "has_ais_gap": True,
                "gap_duration_minutes": 38.0,
                # Module 6 expected states
                "m6_ais_state": "AIS_GAP_DARK",
                "m6_has_kinematic_episodes": False,
                "m6_reachability": "REACHABLE",
                "m6_gap_concurrency_low": True,
            },
            "V004": {
                "re_identifiable_via_dna": True,
                "collective_anomalies": ["COORDINATED_DARK", "RENDEZVOUS"],
                "partner_vessel": "V005",
                # Module 6 expected states
                "m6_ais_state": "AIS_GAP_DARK",
                "m6_has_kinematic_episodes": False,
            },
            "V005": {
                "collective_anomalies": ["COORDINATED_DARK", "RENDEZVOUS"],
                "partner_vessel": "V004",
                # Module 6 expected states
                "m6_ais_state": "AIS_GAP_DARK",
                "m6_has_kinematic_episodes": False,
            },
        },
    }

    with open(GROUND_TRUTH_PATH, mode="w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"[Demo Builder] Wrote ground truth manifest to {GROUND_TRUTH_PATH}")


if __name__ == "__main__":
    generate_demo_dataset()
