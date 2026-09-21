"""
Module 0 — Verification Script (Definition of Done)
Loads every raw data asset and prints shape/row counts with no errors.
Run:  python scripts/verify_data.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
from PIL import Image
import pandas as pd
import sqlite3

from config import SAR_DIR, AIS_DIR, OCEAN_DIR, WIND_DIR, DB_PATH, CASES

print("=" * 62)
print("Occuris MVP — Module 0 Data Verification")
print("=" * 62)

all_ok = True

# ── 1. SAR images + masks ──────────────────────────────────────────────────────
print("\n[1] SAR Images + Masks")
for case_id, case in CASES.items():
    sar_path  = Path(case["sar_image"])
    mask_path = Path(case["sar_mask"])
    try:
        sar  = np.array(Image.open(sar_path).convert("L"))
        mask = np.array(Image.open(mask_path).convert("L"))
        spill_px = int((mask > 127).sum())
        print(f"  {case_id}: SAR shape={sar.shape}  dtype={sar.dtype}  "
              f"mask shape={mask.shape}  spill_pixels={spill_px}")
    except FileNotFoundError as e:
        print(f"  ✗ {case_id}: {e}")
        all_ok = False

# ── 2. AIS data ────────────────────────────────────────────────────────────────
print("\n[2] AIS Sample Data")
try:
    ais = pd.read_csv(AIS_DIR / "ais_sample.csv")
    print(f"  Rows: {len(ais)}  Vessels: {ais['vessel_id'].nunique()}  "
          f"Columns: {list(ais.columns)}")
    for vid, grp in ais.groupby("vessel_id"):
        print(f"    {vid}: {len(grp)} pings  "
              f"lat=[{grp.lat.min():.2f},{grp.lat.max():.2f}]  "
              f"lon=[{grp.lon.min():.2f},{grp.lon.max():.2f}]")
except Exception as e:
    print(f"  ✗ AIS: {e}")
    all_ok = False

# ── 3. Ocean current field ─────────────────────────────────────────────────────
print("\n[3] Ocean Current Field")
try:
    curr = np.load(OCEAN_DIR / "current_arabian_sea.npz")
    U, V = curr["U"], curr["V"]
    print(f"  U shape={U.shape}  U_mean={U.mean():.3f}  U_std={U.std():.3f} m/s")
    print(f"  V shape={V.shape}  V_mean={V.mean():.3f}  V_std={V.std():.3f} m/s")
except Exception as e:
    print(f"  ✗ Current: {e}")
    all_ok = False

# ── 4. Wind field ──────────────────────────────────────────────────────────────
print("\n[4] Wind Field")
try:
    wind = np.load(WIND_DIR / "wind_arabian_sea.npz")
    Uw, Vw = wind["U"], wind["V"]
    print(f"  U shape={Uw.shape}  U_mean={Uw.mean():.3f}  U_std={Uw.std():.3f} m/s")
    print(f"  V shape={Vw.shape}  V_mean={Vw.mean():.3f}  V_std={Vw.std():.3f} m/s")
except Exception as e:
    print(f"  ✗ Wind: {e}")
    all_ok = False

# ── 5. SQLite DB ───────────────────────────────────────────────────────────────
print("\n[5] SQLite Database")
try:
    con = sqlite3.connect(DB_PATH)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"  Tables: {tables}")
    con.close()
except Exception as e:
    print(f"  ✗ DB: {e}")
    all_ok = False

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
if all_ok:
    print("[OK] Module 0 Definition of Done: ALL DATA LOADS SUCCESSFULLY")
else:
    print("[FAIL] Some assets failed -- run generate_synthetic_data.py first")
print("=" * 62)
