"""
Occuris MVP — Central Configuration
3 investigation cases, each tied to one SAR image and one Arabian Sea sub-region.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent

# ── Data paths ─────────────────────────────────────────────────────────────────
DATA_RAW       = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SAR_DIR        = DATA_RAW / "sar"
AIS_DIR        = DATA_RAW / "ais"
OCEAN_DIR      = DATA_RAW / "ocean"
WIND_DIR       = DATA_RAW / "wind"
MODELS_DIR     = ROOT / "models"
DB_PATH        = ROOT / "data" / "occris.db"

# ── Arabian Sea bounding box (shared) ─────────────────────────────────────────
# lon: 58–75 E  |  lat: 14–25 N
ARABIAN_SEA_BBOX = dict(lon_min=58.0, lon_max=75.0, lat_min=14.0, lat_max=25.0)

# ── Case definitions ──────────────────────────────────────────────────────────
# Each case represents one investigation scenario.
# SAR images are PNG (no embedded geo); we assign synthetic centroids here.
CASES = {
    "case_01": {
        "id":            "case_01",
        "title":         "Case 01 — Al-Mahra Corridor Spill",
        "description":   "Suspected discharge in international shipping lane east of Yemen",
        "sar_image":     SAR_DIR / "sar_01.png",
        "sar_mask":      SAR_DIR / "mask_01.png",
        # Synthetic centroid assigned to Arabian Sea sub-region A
        "spill_center":  {"lat": 14.8, "lon": 53.1},   # east of Yemen
        "spill_bbox":    {"lat_min": 14.0, "lat_max": 15.6, "lon_min": 52.2, "lon_max": 54.0},
        "sar_timestamp": "2024-03-15T06:30:00Z",
        "release_window_hours": 24,   # backward drift search window
    },
    "case_02": {
        "id":            "case_02",
        "title":         "Case 02 — Lakshadweep Passage Spill",
        "description":   "Dark vessel activity suspected near Lakshadweep Sea tanker route",
        "sar_image":     SAR_DIR / "sar_02.png",
        "sar_mask":      SAR_DIR / "mask_02.png",
        # Synthetic centroid assigned to Arabian Sea sub-region B
        "spill_center":  {"lat": 17.5, "lon": 69.2},   # western India coast
        "spill_bbox":    {"lat_min": 16.8, "lat_max": 18.2, "lon_min": 68.4, "lon_max": 70.0},
        "sar_timestamp": "2024-04-02T09:15:00Z",
        "release_window_hours": 18,
    },
    "case_03": {
        "id":            "case_03",
        "title":         "Case 03 — Oman Basin Spill",
        "description":   "Multi-source spill signature detected in Oman Basin transit zone",
        "sar_image":     SAR_DIR / "sar_03.png",
        "sar_mask":      SAR_DIR / "mask_03.png",
        # Synthetic centroid assigned to Arabian Sea sub-region C
        "spill_center":  {"lat": 21.3, "lon": 61.8},   # Oman basin
        "spill_bbox":    {"lat_min": 20.5, "lat_max": 22.1, "lon_min": 61.0, "lon_max": 62.6},
        "sar_timestamp": "2024-04-18T04:45:00Z",
        "release_window_hours": 30,
    },
}

# ── SegFormer model settings ──────────────────────────────────────────────────
MODEL_BACKBONE  = "nvidia/mit-b0"
MODEL_CKPT      = MODELS_DIR / "best_segformer_oilspill.pt.zip"  # actual uploaded filename
MODEL_IMG_SIZE  = 256   # matches Kaggle training (IMG_SIZE = 256)
NUM_LABELS      = 2     # 0=background, 1=spill

# ── Drift / OceanParcels settings ─────────────────────────────────────────────
N_PARTICLES     = 50    # seed points sampled from mask
DRIFT_HOURS     = 24    # how far back (or forward) to run parcels
WIND_LEEWAY     = 0.03  # 3 % wind-drift coefficient

# ── AIS settings ──────────────────────────────────────────────────────────────
AIS_CSV         = AIS_DIR / "ais_sample.csv"
GAP_THRESHOLD_MIN = 30  # minutes — gap longer than this → Dark vessel
EKF_MAHAL_THRESH  = 9.0 # chi² 99 % for 2 DOF ≈ 9.21
MAX_VESSEL_SPEED_KN = 18.0  # knots — reachability upper bound

# ── Investigation priority weights ────────────────────────────────────────────
PRIORITY_WEIGHTS = {
    "proximity":           0.15,
    "time_match":          0.15,
    "behaviour_deviation": 0.20,
    "ais_status":          0.20,
    "physical_match":      0.30,
}
PRIORITY_HIGH_THRESH   = 0.65
PRIORITY_MEDIUM_THRESH = 0.35

# ── Gateway polygons (Arabian Sea, synthetic) ─────────────────────────────────
# 4 geofences around the test region entry/exit corridors
GATEWAY_POLYGONS = {
    "gulf_of_aden":     [(41,11),(50,11),(50,15),(41,15)],  # west entrance
    "hormuz_strait":    [(56,24),(60,24),(60,26),(56,26)],  # north entrance
    "west_india_coast": [(72,14),(75,14),(75,22),(72,22)],  # east boundary
    "east_africa_lane": [(58,10),(62,10),(62,16),(58,16)],  # southwest corridor
}
