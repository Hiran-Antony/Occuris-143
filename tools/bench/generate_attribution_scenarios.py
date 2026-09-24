"""
OccurisBench — Synthetic Attribution Scenario Generator (§10)

Generates 300 seed-controlled synthetic scenarios for benchmarking Module 8.
Supports 5 scenario classes:
  1. single_source: 1 true culprit (intersects origin during release window) + 4 bystanders
  2. two_source_coordinated: 2 true culprits (rendezvous / coordinated dark) + 3 bystanders
  3. spoofed_vessel: 1 culprit with kinematic/speed anomaly near origin + 4 bystanders
  4. dark_vessel: 1 culprit with AIS gap reaching origin + 4 bystanders
  5. ambiguous: 2 candidates with overlapping posterior intervals (< 0.05) + 3 bystanders

Each scenario directory contains:
  - ais.csv: synthetic AIS pings for vessels
  - sar_mask.png: synthetic SAR slick mask
  - ground_truth.json: scenario metadata and ground truth labels (ISOLATED from production src/)

Usage:
  python tools/bench/generate_attribution_scenarios.py --scenarios 300 --seed 42 --out data/bench/scenarios
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import struct
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def create_synthetic_sar_png(width: int = 100, height: int = 100) -> bytes:
    """Generate minimal valid grayscale PNG byte sequence with synthetic slick."""
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # filter type 0 (None)
        for x in range(width):
            # Centered elliptical slick
            dx = (x - 50) / 20.0
            dy = (y - 50) / 10.0
            if dx * dx + dy * dy <= 1.0:
                raw_data.append(255)
            else:
                raw_data.append(0)

    compressed = zlib.compress(bytes(raw_data))
    png = bytearray(b"\x89PNG\r\n\x1a\n")
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data)
    png.extend(struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc))
    # IDAT
    idat_crc = zlib.crc32(b"IDAT" + compressed)
    png.extend(struct.pack(">I", len(compressed)) + b"IDAT" + compressed + struct.pack(">I", idat_crc))
    # IEND
    iend_crc = zlib.crc32(b"IEND")
    png.extend(struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc))
    return bytes(png)


def _generate_bystander(
    vessel_id: str,
    mmsi: int,
    base_time: datetime,
    start_lat: float,
    start_lon: float,
    dlat: float,
    dlon: float,
    speed: float,
    course: float,
    v_type: str = "cargo",
) -> List[Dict[str, Any]]:
    """Generate steady transit for innocent bystander vessel far from origin."""
    rows = []
    t = base_time
    lat = start_lat
    lon = start_lon
    for step in range(60):
        rows.append({
            "mmsi": mmsi,
            "vessel_id": vessel_id,
            "vessel_name": f"BYSTANDER {vessel_id}",
            "timestamp": t.isoformat(),
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": round(speed + 0.2 * math.sin(step), 1),
            "cog": round(course, 1),
            "nav_status": 0,
            "source": "AIS_CLASS_A",
        })
        t += timedelta(minutes=10)
        lat += dlat
        lon += dlon
    return rows


def generate_scenario(
    scenario_idx: int,
    scenario_class: str,
    rng: random.Random,
    base_time: datetime,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Generate AIS rows and ground truth manifest for a single scenario."""
    scenario_id = f"scenario_{scenario_idx:03d}"
    
    # Origin location with small deterministic jitter
    origin_lat = round(16.50 + rng.uniform(-0.25, 0.25), 4)
    origin_lon = round(64.50 + rng.uniform(-0.25, 0.25), 4)
    
    all_rows: List[Dict[str, Any]] = []
    culprits: List[str] = []
    bystanders: List[str] = []

    # Bystander templates placed safely away (>40km)
    bystander_configs = [
        ("V003", 477003000 + scenario_idx, origin_lat + 0.60, origin_lon + 0.50, 0.005, -0.040, 12.5, 275.0),
        ("V004", 477004000 + scenario_idx, origin_lat - 0.70, origin_lon - 0.60, -0.040, 0.005, 11.0, 175.0),
        ("V005", 477005000 + scenario_idx, origin_lat + 0.80, origin_lon - 0.70, 0.035, 0.035, 13.0, 45.0),
    ]

    if scenario_class == "single_source":
        culprits = ["V001"]
        bystanders = ["V002", "V003", "V004", "V005"]
        
        # V001: Tanker directly intersects origin zone at step 36 (~06:00 UTC)
        t = base_time
        lat = origin_lat - 36 * (-0.015)
        lon = origin_lon - 36 * (-0.015)
        for step in range(60):
            all_rows.append({
                "mmsi": 477001000 + scenario_idx,
                "vessel_id": "V001",
                "vessel_name": f"CULPRIT TANKER {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "sog": round(13.2 + 0.2 * math.cos(step), 1),
                "cog": 135.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            t += timedelta(minutes=10)
            lat += -0.015
            lon += -0.015

        # V002 bystander (far north)
        all_rows.extend(_generate_bystander(
            "V002", 477002000 + scenario_idx, base_time,
            origin_lat + 0.55, origin_lon - 0.40, -0.004, 0.035, 12.0, 95.0
        ))
        for vid, mmsi, slat, slon, dlat, dlon, spd, crs in bystander_configs:
            all_rows.extend(_generate_bystander(vid, mmsi, base_time, slat, slon, dlat, dlon, spd, crs))

    elif scenario_class == "two_source_coordinated":
        culprits = ["V001", "V002"]
        bystanders = ["V003", "V004", "V005"]

        # V001 and V002 approach and rendezvous near origin (steps 35-39)
        t = base_time
        lat1, lon1 = origin_lat + 0.35, origin_lon - 0.35
        lat2, lon2 = origin_lat - 0.35, origin_lon + 0.35

        for step in range(60):
            is_rdvz = 35 <= step <= 39
            if step < 35:
                lat1 -= 0.010
                lon1 += 0.010
                lat2 += 0.010
                lon2 -= 0.010
                sog1, sog2 = 13.5, 13.0
                cur_lat1, cur_lon1 = lat1, lon1
                cur_lat2, cur_lon2 = lat2, lon2
            elif is_rdvz:
                sog1, sog2 = 1.2, 1.3
                cur_lat1, cur_lon1 = origin_lat, origin_lon
                cur_lat2, cur_lon2 = origin_lat + 0.002, origin_lon + 0.002  # ~250m apart
            else:
                offset = (step - 39) * 0.010
                sog1, sog2 = 12.5, 12.5
                cur_lat1, cur_lon1 = origin_lat - offset, origin_lon + offset
                cur_lat2, cur_lon2 = origin_lat - offset + 0.002, origin_lon + offset + 0.002

            all_rows.append({
                "mmsi": 477001000 + scenario_idx,
                "vessel_id": "V001",
                "vessel_name": f"RDVZ LEAD {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(cur_lat1, 5),
                "lon": round(cur_lon1, 5),
                "sog": round(sog1, 1),
                "cog": 135.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            all_rows.append({
                "mmsi": 477002000 + scenario_idx,
                "vessel_id": "V002",
                "vessel_name": f"RDVZ TENDER {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(cur_lat2, 5),
                "lon": round(cur_lon2, 5),
                "sog": round(sog2, 1),
                "cog": 315.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            t += timedelta(minutes=10)

        for vid, mmsi, slat, slon, dlat, dlon, spd, crs in bystander_configs:
            all_rows.extend(_generate_bystander(vid, mmsi, base_time, slat, slon, dlat, dlon, spd, crs))

    elif scenario_class == "spoofed_vessel":
        culprits = ["V001"]
        bystanders = ["V002", "V003", "V004", "V005"]

        # V001: Tanker with impossible kinematic burst (SOG jump to 36.5 kn) near origin
        t = base_time
        lat = origin_lat - 36 * (-0.015)
        lon = origin_lon - 36 * (-0.015)
        for step in range(60):
            # Kinematic speed spoof at step 34
            sog = 36.5 if step == 34 else 12.8 + 0.2 * math.sin(step)
            all_rows.append({
                "mmsi": 477001000 + scenario_idx,
                "vessel_id": "V001",
                "vessel_name": f"SPOOFED TANKER {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "sog": round(sog, 1),
                "cog": 135.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            t += timedelta(minutes=10)
            lat += -0.015
            lon += -0.015

        all_rows.extend(_generate_bystander(
            "V002", 477002000 + scenario_idx, base_time,
            origin_lat + 0.55, origin_lon - 0.40, -0.004, 0.035, 12.0, 95.0
        ))
        for vid, mmsi, slat, slon, dlat, dlon, spd, crs in bystander_configs:
            all_rows.extend(_generate_bystander(vid, mmsi, base_time, slat, slon, dlat, dlon, spd, crs))

    elif scenario_class == "dark_vessel":
        culprits = ["V001"]
        bystanders = ["V002", "V003", "V004", "V005"]

        # V001: Goes dark (45 min gap) right before origin zone, reaches origin during gap
        t = base_time
        lat = origin_lat - 36 * (-0.015)
        lon = origin_lon - 36 * (-0.015)
        for step in range(60):
            if step == 32:
                # 45 min blackout spanning steps 32 to 36
                t += timedelta(minutes=45)
                lat += -0.060
                lon += -0.060

            all_rows.append({
                "mmsi": 477001000 + scenario_idx,
                "vessel_id": "V001",
                "vessel_name": f"DARK VESSEL {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "sog": round(13.0, 1),
                "cog": 135.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            t += timedelta(minutes=10)
            lat += -0.015
            lon += -0.015

        all_rows.extend(_generate_bystander(
            "V002", 477002000 + scenario_idx, base_time,
            origin_lat + 0.55, origin_lon - 0.40, -0.004, 0.035, 12.0, 95.0
        ))
        for vid, mmsi, slat, slon, dlat, dlon, spd, crs in bystander_configs:
            all_rows.extend(_generate_bystander(vid, mmsi, base_time, slat, slon, dlat, dlon, spd, crs))

    elif scenario_class == "ambiguous":
        # Two vessels cross origin zone with almost identical timing and distance
        culprits = ["V001", "V002"]
        bystanders = ["V003", "V004", "V005"]

        t = base_time
        lat1 = origin_lat - 36 * (-0.015)
        lon1 = origin_lon - 36 * (-0.015)
        lat2 = origin_lat - 36 * (-0.015) + 0.008
        lon2 = origin_lon - 36 * (-0.015) - 0.008

        for step in range(60):
            all_rows.append({
                "mmsi": 477001000 + scenario_idx,
                "vessel_id": "V001",
                "vessel_name": f"AMBIGUOUS A {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(lat1, 5),
                "lon": round(lon1, 5),
                "sog": round(13.0 + 0.1 * math.sin(step), 1),
                "cog": 135.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            all_rows.append({
                "mmsi": 477002000 + scenario_idx,
                "vessel_id": "V002",
                "vessel_name": f"AMBIGUOUS B {scenario_id}",
                "timestamp": t.isoformat(),
                "lat": round(lat2, 5),
                "lon": round(lon2, 5),
                "sog": round(13.1 + 0.1 * math.cos(step), 1),
                "cog": 135.0,
                "nav_status": 0,
                "source": "AIS_CLASS_A",
            })
            t += timedelta(minutes=10)
            lat1 += -0.015
            lon1 += -0.015
            lat2 += -0.015
            lon2 += -0.015

        for vid, mmsi, slat, slon, dlat, dlon, spd, crs in bystander_configs:
            all_rows.extend(_generate_bystander(vid, mmsi, base_time, slat, slon, dlat, dlon, spd, crs))

    # Sort rows by (vessel_id, timestamp)
    all_rows.sort(key=lambda r: (r["vessel_id"], r["timestamp"]))

    # Ground truth manifest with isolation guard
    t_sar = base_time + timedelta(hours=12)
    ground_truth = {
        "_isolation_guard": "GROUND_TRUTH_FOR_TESTS_ONLY",
        "scenario_id": scenario_id,
        "scenario_class": scenario_class,
        "culprits": culprits,
        "bystanders": bystanders,
        "case_context": {
            "case_id": scenario_id,
            "origin_zones": [
                {"lat": origin_lat, "lon": origin_lon, "radius_km": 5.0}
            ],
            "spill_center": {"lat": origin_lat, "lon": origin_lon},
            "release_window_start": base_time.isoformat(),
            "release_window_end": t_sar.isoformat(),
            "sar_acquisition_time": t_sar.isoformat(),
            "release_window_hours": 24,
        },
    }

    return all_rows, ground_truth


def generate_scenarios(
    num_scenarios: int = 300,
    seed: int = 42,
    output_dir: Path | str = "data/bench/scenarios",
) -> List[Dict[str, Any]]:
    """Generate seed-controlled synthetic benchmark scenarios."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    
    classes = [
        "single_source",
        "two_source_coordinated",
        "spoofed_vessel",
        "dark_vessel",
        "ambiguous",
    ]

    base_time = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    sar_png = create_synthetic_sar_png()
    manifest_items = []

    print(f"[OccurisBench] Generating {num_scenarios} scenarios (seed={seed}) into {out_path}...")
    for idx in range(1, num_scenarios + 1):
        s_class = classes[(idx - 1) % len(classes)]
        rows, gt = generate_scenario(idx, s_class, rng, base_time)
        
        scenario_dir = out_path / f"scenario_{idx:03d}"
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Write ais.csv
        csv_path = scenario_dir / "ais.csv"
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "mmsi", "vessel_id", "vessel_name", "timestamp",
                "lat", "lon", "sog", "cog", "nav_status", "source"
            ])
            writer.writeheader()
            writer.writerows(rows)

        # Write sar_mask.png
        mask_path = scenario_dir / "sar_mask.png"
        mask_path.write_bytes(sar_png)

        # Write ground_truth.json
        gt_path = scenario_dir / "ground_truth.json"
        with open(gt_path, mode="w", encoding="utf-8") as f:
            json.dump(gt, f, indent=2)

        manifest_items.append({
            "scenario_id": gt["scenario_id"],
            "scenario_class": s_class,
            "culprits": gt["culprits"],
            "bystanders": gt["bystanders"],
            "dir": str(scenario_dir),
        })

    # Write root benchmark manifest
    root_manifest = {
        "benchmark": "OccurisBench",
        "version": "1.0.0",
        "total_scenarios": num_scenarios,
        "seed": seed,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classes_distribution": {c: num_scenarios // len(classes) for c in classes},
        "scenarios": manifest_items,
    }
    with open(out_path / "bench_manifest.json", mode="w", encoding="utf-8") as f:
        json.dump(root_manifest, f, indent=2)

    print(f"[OccurisBench] Completed generation of {num_scenarios} scenarios.")
    return manifest_items


def main():
    parser = argparse.ArgumentParser(description="OccurisBench Scenario Generator")
    parser.add_argument("--scenarios", type=int, default=300, help="Number of scenarios to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--out", type=str, default="data/bench/scenarios", help="Output directory")
    args = parser.parse_args()

    generate_scenarios(num_scenarios=args.scenarios, seed=args.seed, output_dir=args.out)


if __name__ == "__main__":
    main()
