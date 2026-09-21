"""
Module 0 — Synthetic Data Generator
Generates all raw data the Occuris pipeline needs:
  - 3 SAR PNG images (512×512, grayscale) with elliptical spill patches
  - 3 binary mask PNGs
  - 1 synthetic AIS CSV (500 rows, 5 vessels, deliberate anomalies)
  - 1 synthetic ocean-current field  (numpy npz)
  - 1 synthetic wind field           (numpy npz)
  - SQLite DB schema

Run:  python scripts/generate_synthetic_data.py
"""

import sys, sqlite3, random, math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import (
    SAR_DIR, AIS_DIR, OCEAN_DIR, WIND_DIR, DB_PATH,
    CASES, ARABIAN_SEA_BBOX
)


# ── helpers ────────────────────────────────────────────────────────────────────

def draw_spill_ellipse(draw, cx, cy, rx, ry, angle_deg, noise_rng):
    """Draw a noisy elliptical spill patch onto an ImageDraw context."""
    pts = []
    for t in np.linspace(0, 2 * math.pi, 120):
        x = rx * math.cos(t)
        y = ry * math.sin(t)
        # rotate
        ang = math.radians(angle_deg)
        xr = x * math.cos(ang) - y * math.sin(ang)
        yr = x * math.sin(ang) + y * math.cos(ang)
        # add boundary noise
        noise = noise_rng.uniform(-6, 6)
        pts.append((cx + xr + noise, cy + yr + noise))
    draw.polygon(pts, fill=200)


def make_sar_and_mask(seed: int, img_size=512):
    rng = np.random.default_rng(seed)
    noise_rng = random.Random(seed)

    # --- SAR background: textured sea clutter ---
    bg = rng.normal(70, 18, (img_size, img_size)).clip(0, 255).astype(np.uint8)
    sar = Image.fromarray(bg, mode="L")
    mask_arr = np.zeros((img_size, img_size), dtype=np.uint8)

    draw_sar  = ImageDraw.Draw(sar)
    draw_mask = ImageDraw.Draw(Image.fromarray(mask_arr))

    # random number of spill patches (1 or 2 to match case 3 = two-source)
    n_patches = 2 if seed == 42 else 1

    for _ in range(n_patches):
        cx  = rng.integers(100, img_size - 100)
        cy  = rng.integers(100, img_size - 100)
        rx  = rng.integers(40, 110)
        ry  = rng.integers(25, 70)
        ang = rng.integers(0, 180)
        # SAR spill is DARKER than sea (oil dampens radar backscatter)
        pts = []
        for t in np.linspace(0, 2 * math.pi, 120):
            x = rx * math.cos(t); y = ry * math.sin(t)
            a = math.radians(ang)
            xr = x * math.cos(a) - y * math.sin(a)
            yr = x * math.sin(a) + y * math.cos(a)
            noise = noise_rng.uniform(-5, 5)
            pts.append((cx + xr + noise, cy + yr + noise))
        draw_sar.polygon(pts, fill=30)  # dark patch

        # --- build mask on numpy array directly ---
        from PIL import Image as PILImage
        tmp_mask = PILImage.new("L", (img_size, img_size), 0)
        tmp_draw = ImageDraw.Draw(tmp_mask)
        tmp_draw.polygon(pts, fill=255)
        mask_arr = np.maximum(mask_arr, np.array(tmp_mask))

    # slight blur to look more realistic
    sar = sar.filter(ImageFilter.GaussianBlur(radius=1))
    mask_img = Image.fromarray(mask_arr, mode="L")
    return sar, mask_img


# ── Module 0A — SAR images + masks ────────────────────────────────────────────

def generate_sar_images():
    SAR_DIR.mkdir(parents=True, exist_ok=True)
    seeds = {"case_01": 7, "case_02": 13, "case_03": 42}   # 42 → two patches
    for case_id, seed in seeds.items():
        idx = case_id.split("_")[1]
        sar, mask = make_sar_and_mask(seed)
        sar_path  = SAR_DIR / f"sar_{idx}.png"
        mask_path = SAR_DIR / f"mask_{idx}.png"
        sar.save(sar_path)
        mask.save(mask_path)
        print(f"  [SAR] {sar_path.name}  {sar.size}  mask_pixels={np.array(mask).sum()//255}")


# ── Module 0B — Synthetic AIS CSV ─────────────────────────────────────────────

def generate_ais():
    AIS_DIR.mkdir(parents=True, exist_ok=True)

    import datetime

    vessels = {
        "V001": {"name": "NORMAL TRADER",    "mmsi": 477001001, "behaviour": "normal"},
        "V002": {"name": "GULF CARRIER",     "mmsi": 477001002, "behaviour": "dark"},     # 35-min gap
        "V003": {"name": "ARABIAN PHANTOM",  "mmsi": 477001003, "behaviour": "spoofed"},  # implausible jump
        "V004": {"name": "TRUE SOURCE",      "mmsi": 477001004, "behaviour": "normal"},   # matches spill
        "V005": {"name": "INNOCENT TRANSIT", "mmsi": 477001005, "behaviour": "normal"},   # nearby but innocent
    }

    records = []
    base_dt = datetime.datetime(2024, 3, 15, 0, 0, 0)

    rng = np.random.default_rng(99)

    for vid, vinfo in vessels.items():
        # start positions roughly in Arabian Sea
        lat = rng.uniform(15, 23)
        lon = rng.uniform(58, 72)
        cog = rng.uniform(60, 300)   # degrees
        sog = rng.uniform(8, 14)     # knots

        t = base_dt
        gap_injected = False
        jump_injected = False
        ping_count = 0

        while (t - base_dt).total_seconds() < 12 * 3600:
            interval_min = rng.integers(5, 12)

            # Dark vessel: inject a 35-min gap around hour 3
            if vinfo["behaviour"] == "dark" and not gap_injected and (t - base_dt).total_seconds() > 3 * 3600:
                t += datetime.timedelta(minutes=35)
                gap_injected = True
                continue

            # Spoofed: inject an implausible 150-nm jump at hour 2
            if vinfo["behaviour"] == "spoofed" and not jump_injected and (t - base_dt).total_seconds() > 2 * 3600:
                lat += rng.uniform(1.8, 2.5)   # ~150–200 nm jump
                lon += rng.uniform(1.8, 2.5)
                jump_injected = True

            records.append({
                "mmsi":          vinfo["mmsi"],
                "vessel_id":     vid,
                "vessel_name":   vinfo["name"],
                "timestamp":     t.isoformat() + "Z",
                "lat":           round(float(lat), 5),
                "lon":           round(float(lon), 5),
                "sog":           round(float(sog), 1),
                "cog":           round(float(cog), 1),
                "nav_status":    0,   # under way using engine
                "source":        "AIS_CLASS_A",
            })

            # advance position
            dt_hr = interval_min / 60.0
            dlat  = sog * math.cos(math.radians(cog)) * dt_hr / 60.0
            dlon  = sog * math.sin(math.radians(cog)) * dt_hr / 60.0 / math.cos(math.radians(lat))
            lat  += dlat + rng.normal(0, 0.001)
            lon  += dlon + rng.normal(0, 0.001)
            cog  += rng.normal(0, 2)
            sog  += rng.normal(0, 0.3)
            sog   = float(np.clip(sog, 2, 18))

            t += datetime.timedelta(minutes=int(interval_min))
            ping_count += 1

    df = pd.DataFrame(records)
    df.to_csv(AIS_DIR / "ais_sample.csv", index=False)
    print(f"  [AIS] ais_sample.csv  {len(df)} rows  vessels={df['vessel_id'].nunique()}")


# ── Module 0C — Synthetic ocean current + wind fields ─────────────────────────

def generate_fields():
    OCEAN_DIR.mkdir(parents=True, exist_ok=True)
    WIND_DIR.mkdir(parents=True, exist_ok=True)

    nlat, nlon = 56, 85   # 0.25° resolution over Arabian Sea
    lats = np.linspace(ARABIAN_SEA_BBOX["lat_min"], ARABIAN_SEA_BBOX["lat_max"], nlat)
    lons = np.linspace(ARABIAN_SEA_BBOX["lon_min"], ARABIAN_SEA_BBOX["lon_max"], nlon)
    LON, LAT = np.meshgrid(lons, lats)

    # Simulate NE monsoon: currents flowing SW (negative U, negative V)
    U_curr = -0.3 + 0.05 * np.sin(2 * np.pi * (LAT - 14) / 11) + np.random.default_rng(1).normal(0, 0.02, (nlat, nlon))
    V_curr = -0.15 + 0.03 * np.cos(2 * np.pi * (LON - 58) / 17) + np.random.default_rng(2).normal(0, 0.01, (nlat, nlon))

    # Wind: NE monsoon direction, ~7 m/s
    U_wind = -5.5 + np.random.default_rng(3).normal(0, 0.5, (nlat, nlon))
    V_wind = -4.0 + np.random.default_rng(4).normal(0, 0.4, (nlat, nlon))

    np.savez(OCEAN_DIR / "current_arabian_sea.npz", U=U_curr, V=V_curr, lats=lats, lons=lons)
    np.savez(WIND_DIR  / "wind_arabian_sea.npz",    U=U_wind, V=V_wind, lats=lats, lons=lons)
    print(f"  [CURRENT] shape={U_curr.shape}  U_mean={U_curr.mean():.3f}  V_mean={V_curr.mean():.3f} m/s")
    print(f"  [WIND]    shape={U_wind.shape}  U_mean={U_wind.mean():.3f}  V_mean={V_wind.mean():.3f} m/s")


# ── Module 0D — SQLite schema ──────────────────────────────────────────────────

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS vessels (
        vessel_id   TEXT PRIMARY KEY,
        mmsi        INTEGER,
        name        TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS ais_pings (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        vessel_id   TEXT REFERENCES vessels(vessel_id),
        timestamp   TEXT,
        lat         REAL,
        lon         REAL,
        sog         REAL,
        cog         REAL,
        nav_status  INTEGER,
        source      TEXT
    );

    CREATE TABLE IF NOT EXISTS spills (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id         TEXT,
        sar_timestamp   TEXT,
        center_lat      REAL,
        center_lon      REAL,
        area_km2        REAL,
        perimeter_km    REAL,
        orientation_deg REAL,
        mask_path       TEXT,
        geometry_json   TEXT
    );

    CREATE TABLE IF NOT EXISTS origin_zones (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        spill_id        INTEGER REFERENCES spills(id),
        center_lat      REAL,
        center_lon      REAL,
        ellipse_a_km    REAL,
        ellipse_b_km    REAL,
        ellipse_ang_deg REAL,
        release_time_start TEXT,
        release_time_end   TEXT,
        source_hypothesis  TEXT   -- 'one_source' or 'two_sources'
    );

    CREATE TABLE IF NOT EXISTS investigations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id         TEXT,
        vessel_id       TEXT REFERENCES vessels(vessel_id),
        priority        TEXT,   -- 'High' / 'Medium' / 'Low'
        score_total     REAL,
        score_proximity REAL,
        score_time      REAL,
        score_behaviour REAL,
        score_ais       REAL,
        score_physical  REAL,
        ais_classification TEXT, -- 'Normal' / 'AIS Gap (Dark)' / 'Spoofed'
        reachability_km REAL,
        created_at      TEXT DEFAULT (datetime('now'))
    );
    """)
    con.commit()
    con.close()
    print(f"  [DB] {DB_PATH}  schema initialized")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Occuris MVP — Generating synthetic data…")
    print("=" * 60)
    generate_sar_images()
    generate_ais()
    generate_fields()
    init_db()
    print("=" * 60)
    print("Done. Run scripts/verify_data.py to confirm Module 0 DoD.")
