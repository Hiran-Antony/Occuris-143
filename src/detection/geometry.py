"""
Module 2 — Look-Alike Verification & Spill Geometry
Computes:
  - Look-alike filter: contrast ratio (mean intensity inside vs outside mask)
    A genuine oil spill has LOWER backscatter than surrounding sea.
    Upgradeable to VV/VH ratio if real dual-pol Sentinel-1 is available.
  - Spill geometry: area (px^2 + km^2), perimeter, centroid, PCA orientation,
    bounding ellipse semi-axes.

Usage:
  python src/detection/geometry.py
  python src/detection/geometry.py --case case_01
  # Or import: from detection.geometry import compute_geometry
"""
import sys, argparse, json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
from PIL import Image
from scipy.ndimage import label as ndlabel
from sklearn.decomposition import PCA
from shapely.geometry import MultiPoint, Polygon
import shapely.affinity

from config import CASES, DATA_PROCESSED


# ── Constants ──────────────────────────────────────────────────────────────────
# Pixel scale for synthetic images assigned to Arabian Sea
# We assign 10m / pixel — synthetic, consistent across all 3 cases.
PIXEL_SCALE_M = 10.0  # metres per pixel (Sentinel-1 IW mode ≈ 10m)
M_PER_NM      = 1852.0

# Look-alike filter threshold: ratio < this = likely spill (dark patch)
LOOKALIKE_RATIO_THRESH = 0.85   # inside_mean / outside_mean < 0.85 → pass


def load_mask(case_id: str, from_pred=False) -> np.ndarray:
    """
    Load binary mask. 
    from_pred=True  → use model-predicted mask from data/processed/
    from_pred=False → use ground-truth mask from data/raw/sar/
    """
    if from_pred:
        p = DATA_PROCESSED / f"{case_id}_pred_mask.npy"
        if p.exists():
            return np.load(p)
    # Fall back to ground-truth mask
    mask_path = Path(CASES[case_id]["sar_mask"])
    arr = np.array(Image.open(mask_path).convert("L"))
    return (arr > 127).astype(np.uint8)


def load_sar(case_id: str) -> np.ndarray:
    sar_path = Path(CASES[case_id]["sar_image"])
    return np.array(Image.open(sar_path).convert("L"), dtype=np.float32)


# ── Look-alike filter ──────────────────────────────────────────────────────────

def lookalike_filter(sar: np.ndarray, mask: np.ndarray) -> dict:
    """
    Contrast-based look-alike filter.
    Oil spill: dark patch → inside_mean < outside_mean.
    Returns: ratio, verdict ('pass' | 'reject'), explanation.
    """
    inside_pixels  = sar[mask == 1]
    outside_pixels = sar[mask == 0]

    if len(inside_pixels) == 0:
        return {"verdict": "reject", "reason": "empty mask", "ratio": None}

    inside_mean  = float(inside_pixels.mean())
    outside_mean = float(outside_pixels.mean())
    ratio = inside_mean / (outside_mean + 1e-6)

    verdict = "pass" if ratio < LOOKALIKE_RATIO_THRESH else "reject"
    reason  = (
        f"inside_mean={inside_mean:.1f} < outside_mean={outside_mean:.1f} "
        f"(ratio={ratio:.3f} < {LOOKALIKE_RATIO_THRESH})"
        if verdict == "pass"
        else
        f"inside_mean={inside_mean:.1f} >= outside_mean*{LOOKALIKE_RATIO_THRESH:.2f} "
        f"(ratio={ratio:.3f}) → possible look-alike (wind slick / ship wake)"
    )
    return {"verdict": verdict, "ratio": round(ratio, 4),
            "inside_mean": round(inside_mean, 2), "outside_mean": round(outside_mean, 2),
            "reason": reason}


# ── Spill geometry ──────────────────────────────────────────────────────────────

def compute_geometry(case_id: str, mask: np.ndarray,
                     sar: np.ndarray = None) -> dict:
    """
    Extract geometric properties from a binary spill mask.
    Returns a dict with area, perimeter, centroid, orientation, ellipse parameters.
    """
    px_m = PIXEL_SCALE_M

    # ── Pixels & area ──────────────────────────────────────────────────────────
    spill_pixels = np.argwhere(mask == 1)  # (N, 2) array of (row, col)
    n_pix        = len(spill_pixels)
    area_px2     = float(n_pix)
    area_m2      = area_px2 * (px_m ** 2)
    area_km2     = area_m2 / 1e6

    # ── Perimeter (count boundary pixels) ─────────────────────────────────────
    from scipy.ndimage import binary_erosion
    eroded       = binary_erosion(mask).astype(np.uint8)
    border       = mask - eroded
    perimeter_px = float(border.sum())
    perimeter_km = perimeter_px * px_m / 1000.0

    # ── Centroid ───────────────────────────────────────────────────────────────
    rows, cols   = spill_pixels[:, 0], spill_pixels[:, 1]
    centroid_px  = (float(rows.mean()), float(cols.mean()))

    # Convert pixel centroid to synthetic lat/lon using case bbox
    bbox = CASES[case_id]["spill_bbox"]
    H, W = mask.shape
    centroid_lat = bbox["lat_max"] - (centroid_px[0] / H) * (bbox["lat_max"] - bbox["lat_min"])
    centroid_lon = bbox["lon_min"] + (centroid_px[1] / W) * (bbox["lon_max"] - bbox["lon_min"])

    # ── Orientation via PCA ────────────────────────────────────────────────────
    if n_pix >= 3:
        pts = spill_pixels.astype(np.float64)
        pca = PCA(n_components=2).fit(pts)
        angle_rad = np.arctan2(pca.components_[0, 1], pca.components_[0, 0])
        orientation_deg = float(np.degrees(angle_rad)) % 180.0
        # Semi-axes from explained variance (std dev along each PC)
        semi_major_px = float(np.sqrt(pca.explained_variance_[0]) * 2)
        semi_minor_px = float(np.sqrt(pca.explained_variance_[1]) * 2)
        semi_major_km = semi_major_px * px_m / 1000.0
        semi_minor_km = semi_minor_px * px_m / 1000.0
    else:
        orientation_deg = 0.0
        semi_major_km = semi_minor_km = 0.0

    # ── Look-alike filter ──────────────────────────────────────────────────────
    lookalike = lookalike_filter(sar, mask) if sar is not None else {"verdict": "skipped"}

    result = {
        "case_id":          case_id,
        "spill_pixels":     int(n_pix),
        "area_km2":         round(area_km2, 4),
        "perimeter_km":     round(perimeter_km, 4),
        "centroid_lat":     round(centroid_lat, 5),
        "centroid_lon":     round(centroid_lon, 5),
        "orientation_deg":  round(orientation_deg, 2),
        "semi_major_km":    round(semi_major_km, 4),
        "semi_minor_km":    round(semi_minor_km, 4),
        "lookalike":        lookalike,
    }
    return result


def run_geometry(case_ids=None):
    ids = case_ids if case_ids else list(CASES.keys())
    all_results = {}

    print(f"\n{'='*62}")
    print(f"Module 2 -- Look-Alike Verification & Spill Geometry")
    print(f"{'='*62}")
    print(f"  Pixel scale: {PIXEL_SCALE_M}m/px  "
          f"Look-alike threshold: {LOOKALIKE_RATIO_THRESH}")

    for case_id in ids:
        mask = load_mask(case_id, from_pred=False)
        sar  = load_sar(case_id)
        geom = compute_geometry(case_id, mask, sar)
        all_results[case_id] = geom

        la = geom["lookalike"]
        print(f"\n  [{case_id}]")
        print(f"    Spill pixels : {geom['spill_pixels']}")
        print(f"    Area         : {geom['area_km2']} km^2")
        print(f"    Perimeter    : {geom['perimeter_km']} km")
        print(f"    Centroid     : lat={geom['centroid_lat']}  lon={geom['centroid_lon']}")
        print(f"    Orientation  : {geom['orientation_deg']} deg (PCA principal axis)")
        print(f"    Ellipse      : a={geom['semi_major_km']} km  b={geom['semi_minor_km']} km")
        print(f"    Look-alike   : [{la.get('verdict','?').upper()}]  {la.get('reason','')}")

        # Save geometry JSON for downstream modules
        out = DATA_PROCESSED / f"{case_id}_geometry.json"
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(geom, indent=2))

    print(f"\n[OK] Module 2 Definition of Done: geometry computed for all {len(ids)} cases.")
    print(f"{'='*62}\n")
    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, default=None)
    args = parser.parse_args()
    run_geometry(case_ids=[args.case] if args.case else None)
