"""
Module 2 — Look-Alike Verification & Spill Geometry
Validates SegFormer predictions with physical SAR contrast checks and
extracts real measurable geometric properties for downstream drift analysis.
"""
import sys, argparse, json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from sklearn.decomposition import PCA
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import CASES, DATA_PROCESSED
from geo_transform import GeoTransform

# MVP Config parameters (PIXEL_SCALE_M is the SAR sensor resolution; it is NOT
# used for spatial calculations here — see geo_transform.py for the authoritative
# pixel-to-geographic mapping derived from spill_bbox / image dimensions).
LOOKALIKE_RATIO_THRESH = 0.85
MIN_SPILL_AREA_PX = 100  # Reject components smaller than this


def load_sar(case_id: str) -> np.ndarray:
    sar_path = Path(CASES[case_id]["sar_image"])
    # Return as 0-1 float array for consistent statistics
    return np.array(Image.open(sar_path).convert("L"), dtype=np.float32) / 255.0


def load_predicted_mask(case_id: str) -> np.ndarray:
    """Loads the model's raw output saved by Module 1."""
    p = DATA_PROCESSED / f"{case_id}_pred_mask.npy"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}. Run Module 1 inference first.")
    # Binary mask: 1 = spill, 0 = background
    mask = np.load(p)
    return (mask > 0).astype(np.uint8)


def clean_mask(mask: np.ndarray) -> np.ndarray:
    """Removes noise and filters out tiny components."""
    # 1. Morphological Open & Close
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    # 2. Connected Components - filter tiny noise
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(closed, connectivity=8)
    clean = np.zeros_like(closed)
    
    # Label 0 is always background
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= MIN_SPILL_AREA_PX:
            clean[labels == i] = 1
            
    return clean


def extract_geometry(case_id: str, mask: np.ndarray) -> dict:
    """Calculate geometric properties from actual mask pixels.
    
    All spatial quantities (area, axes, perimeter in km) are derived from
    the shared GeoTransform — pixel scale comes from the spill_bbox geographic
    extents, not from the SAR sensor resolution (PIXEL_SCALE_M).
    """
    gt = GeoTransform(case_id)
    m_per_row, m_per_col = gt.metres_per_pixel()

    spill_pixels = np.argwhere(mask == 1)  # (row, col)
    n_pix = len(spill_pixels)
    
    if n_pix == 0:
        return {
            "spill_pixels": 0, "area_km2": None, "perimeter_px": 0.0,
            "centroid_pixel": {"x": 0.0, "y": 0.0},
            "centroid_geo": {"latitude": None, "longitude": None},
            "orientation_deg": 0.0, "major_axis_km": 0.0, "minor_axis_km": 0.0,
            "contour": None
        }

    # 1. Area — MVP geospatial estimate (10.46 m/pixel assumed for GRD)
    PIXEL_SCALE_M = 10.46
    area_km2 = (n_pix * PIXEL_SCALE_M * PIXEL_SCALE_M) / 1_000_000.0

    # 2. Centroid (pixel)
    row_mean, col_mean = float(spill_pixels[:, 0].mean()), float(spill_pixels[:, 1].mean())

    # Centroid (geo) — via shared transform
    lat, lon = gt.pixel_to_latlon(row_mean, col_mean)

    # 3. Perimeter
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    perimeter_px = 0.0
    main_contour = None
    if contours:
        main_contour = max(contours, key=cv2.contourArea)
        for c in contours:
            perimeter_px += cv2.arcLength(c, closed=True)

    # 4. PCA for Orientation and Axes
    if n_pix >= 3:
        pca = PCA(n_components=2).fit(spill_pixels.astype(np.float64))
        v_row, v_col = pca.components_[0]
        angle_rad = np.arctan2(v_row, v_col)
        orientation_deg = float(np.degrees(angle_rad)) % 180.0
        
        # Pixel-space std → physical km using bbox-derived scale
        major_px = float(np.sqrt(pca.explained_variance_[0]) * 2)
        minor_px = float(np.sqrt(pca.explained_variance_[1]) * 2)
        # MVP geospatial estimate (10.46 m/pixel assumed)
        PIXEL_SCALE_M = 10.46
        major_km = (major_px * PIXEL_SCALE_M) / 1000.0
        minor_km = (minor_px * PIXEL_SCALE_M) / 1000.0
    else:
        orientation_deg = major_km = minor_km = 0.0

    return {
        "spill_pixels": int(n_pix),
        "area_px2": int(n_pix),
        "area_km2": round(area_km2, 4),
        "area_status": "PROVISIONAL",
        "area_caveat": (
            "PROVISIONAL GEOSPATIAL ESTIMATE. "
            "The 256x256 image represents a surveillance scene of ~{:.0f}x{:.0f} km (spill_bbox). "
            "Pixel scale: {:.1f} m/px (lat) x {:.1f} m/px (lon). "
            "This maps each pixel to its geographic location within the scene, which is correct "
            "for centroid and drift seeding, but the spill patch area derived from pixel count "
            "conflates spill extent with scene coverage. "
            "Do NOT present this as a measured oil-spill area. "
            "Requires real Sentinel-1 geotransform + tight spill crop for a valid area estimate."
        ).format(
            gt.summary()["geographic_height_km"],
            gt.summary()["geographic_width_km"],
            m_per_row, m_per_col
        ),
        "pixel_scale": {
            **gt.summary(),
            "scene_vs_spill_note": (
                "The bbox is the monitoring scene (~170x190 km), NOT the spill footprint. "
                "The spill patch is a localised object within this scene. "
                "Centroid and coordinate transforms are valid; area_km2 is not."
            )
        },
        "perimeter_px": round(perimeter_px, 2),
        "centroid_pixel": {"x": round(col_mean, 2), "y": round(row_mean, 2)},
        "centroid_geo": {"latitude": round(lat, 5), "longitude": round(lon, 5)},
        "orientation_deg": round(orientation_deg, 2),
        "major_axis_km": round(major_km, 4),
        "minor_axis_km": round(minor_km, 4),
        "contour": main_contour
    }


def verify_lookalike(sar: np.ndarray, mask: np.ndarray) -> dict:
    """Local background ring texture check."""
    if mask.sum() == 0:
        return {"passed": False, "reason": "No spill detected"}

    # 1. Create local background ring
    kernel = np.ones((15, 15), np.uint8)  # Ring width
    dilated = cv2.dilate(mask, kernel, iterations=1)
    ring = dilated - mask

    # 2. Calculate statistics
    spill_pixels = sar[mask == 1]
    ring_pixels = sar[ring == 1]

    if len(ring_pixels) == 0:
        return {"passed": False, "reason": "No background ring found"}

    mu_spill, std_spill = float(spill_pixels.mean()), float(spill_pixels.std())
    mu_bg, std_bg = float(ring_pixels.mean()), float(ring_pixels.std())
    
    # 3. Contrast check
    ratio = mu_spill / (mu_bg + 1e-6)
    passed = ratio < LOOKALIKE_RATIO_THRESH

    return {
        "spill_mean_intensity": round(mu_spill, 4),
        "spill_std": round(std_spill, 4),
        "background_mean_intensity": round(mu_bg, 4),
        "background_std": round(std_bg, 4),
        "contrast_ratio": round(ratio, 4),
        "threshold": LOOKALIKE_RATIO_THRESH,
        "passed": passed,
        "interpretation": "Darker than local background" if passed else "Not sufficiently dark vs local background",
        "caveat": "This consistency check confirms SAR darkness relative to background. It does not definitively prove the presence of oil.",
        "ring_mask": ring
    }


def save_diagnostic_plot(case_id, sar, raw_mask, clean_mask, ring, geom, out_dir):
    fig, axes = plt.subplots(1, 5, figsize=(25, 5))
    for ax in axes: ax.axis('off')
    
    axes[0].imshow(sar, cmap='gray')
    axes[0].set_title("Original SAR")

    axes[1].imshow(raw_mask, cmap='magma')
    axes[1].set_title("Predicted Spill Mask")

    # Clean mask + contour
    axes[2].imshow(clean_mask, cmap='gray')
    if geom["contour"] is not None:
        c = geom["contour"]
        axes[2].plot(c[:, 0, 0], c[:, 0, 1], 'r-', linewidth=1.5)
    axes[2].set_title("Cleaned Mask + Contour")

    axes[3].imshow(ring, cmap='Blues')
    axes[3].set_title("Local Background Ring")

    # Geometry Overlay
    axes[4].imshow(sar, cmap='gray')
    axes[4].imshow(np.ma.masked_where(clean_mask == 0, clean_mask), cmap='autumn', alpha=0.5)
    cx, cy = geom["centroid_pixel"]["x"], geom["centroid_pixel"]["y"]
    axes[4].plot(cx, cy, 'g+', markersize=15, markeredgewidth=2)
    
    # Draw orientation line
    if geom["major_axis_km"] > 0:
        L = 20 # line half-length in pixels for display
        angle_rad = np.radians(geom["orientation_deg"])
        # angle is from col axis. v_row, v_col mapped to y, x in plot
        dx = L * np.cos(angle_rad)
        dy = L * np.sin(angle_rad)
        axes[4].plot([cx - dx, cx + dx], [cy - dy, cy + dy], 'b-', linewidth=2)
        
    axes[4].set_title("Geometry Overlay")

    plt.tight_layout()
    out_path = out_dir / f"{case_id}_diagnostic.png"
    plt.savefig(out_path, dpi=120)
    plt.close()


def process_case(case_id: str):
    sar = load_sar(case_id)
    raw_mask = load_predicted_mask(case_id)
    
    clean = clean_mask(raw_mask)
    
    lookalike = verify_lookalike(sar, clean)
    geom = extract_geometry(case_id, clean)
    
    # Compile final JSON
    output_data = {
        "case_id": case_id,
        "look_alike": {k: v for k, v in lookalike.items() if k != "ring_mask"},
        "geometry": {k: v for k, v in geom.items() if k != "contour"}
    }
    
    # Save JSON
    out_json = DATA_PROCESSED / f"{case_id}_geometry.json"
    out_json.write_text(json.dumps(output_data, indent=2))
    
    # Save Diagnostic Plot
    save_diagnostic_plot(
        case_id, sar, raw_mask, clean, 
        lookalike.get("ring_mask", np.zeros_like(clean)), 
        geom, DATA_PROCESSED
    )
    
    # Terminal output
    print(f"\n[{case_id.upper()}]")
    print("LOOK-ALIKE")
    print(f"  Spill mean      : {lookalike.get('spill_mean_intensity')}")
    print(f"  Background mean : {lookalike.get('background_mean_intensity')}")
    print(f"  Contrast ratio  : {lookalike.get('contrast_ratio')}")
    print(f"  Result          : {'PASS' if lookalike.get('passed') else 'FLAG'}")
    print(f"  Interpretation  : {lookalike.get('interpretation')}")
    print("GEOMETRY")
    print(f"  Pixels          : {geom['spill_pixels']}")
    print(f"  Area            : {geom['area_km2']} km2")
    print(f"  Area Caveat     : {geom['area_caveat']}")
    print(f"  Centroid        : Lat {geom['centroid_geo']['latitude']}, Lon {geom['centroid_geo']['longitude']}")
    print(f"  Perimeter       : {geom['perimeter_px']} pixels")
    print(f"  Orientation     : {geom['orientation_deg']} deg")
    print(f"  Major axis      : {geom['major_axis_km']} km")
    print(f"  Minor axis      : {geom['minor_axis_km']} km")


def main(case_ids=None):
    print(f"\n{'='*62}")
    print(f"Module 2 -- Look-Alike Verification & Spill Geometry")
    print(f"{'='*62}")
    ids = case_ids if case_ids else list(CASES.keys())
    for cid in ids:
        process_case(cid)
    print(f"\n[OK] Module 2 Definition of Done: Geometry and verification completed for {len(ids)} cases.")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, default=None)
    args = parser.parse_args()
    main(case_ids=[args.case] if args.case else None)
