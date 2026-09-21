"""
Module 3 — Stratified Particle Seeding
Extracts representative seed particles from the cleaned SAR spill mask.
Uses stratified sampling (70% interior, 30% boundary) and maps pixel coordinates
to physical geographic coordinates using the true SAR pixel resolution (PIXEL_SCALE_M = 10.0 m/px).
"""
import math
import json
from pathlib import Path
from typing import Tuple, Dict, Any
import numpy as np
import cv2
from PIL import Image

from config import (
    CASES, DATA_PROCESSED, N_PARTICLES,
    STRATIFIED_INTERIOR_RATIO, PIXEL_SCALE_M
)

M_PER_DEG_LAT = 111_320.0

def sample_stratified_seed_points(
    case_id: str,
    n_particles: int = N_PARTICLES,
    interior_ratio: float = STRATIFIED_INTERIOR_RATIO,
    seed: int = 42
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Samples N particles using stratified sampling across spill interior and perimeter.
    Uses PIXEL_SCALE_M (10.0 m/px) centered on the case's geographic centroid.
    
    Returns:
        seed_lats: 1D array of initial latitudes
        seed_lons: 1D array of initial longitudes
        meta: dictionary with sampling details
    """
    # 1. Load mask: prefer Module 1 cleaned/pred mask, fall back to raw SAR mask
    pred_path = DATA_PROCESSED / f"{case_id}_pred_mask.npy"
    if pred_path.exists():
        raw_mask = np.load(pred_path)
        mask = (raw_mask > 0).astype(np.uint8)
    else:
        sar_mask_path = Path(CASES[case_id]["sar_mask"])
        if not sar_mask_path.exists():
            raise FileNotFoundError(f"Neither {pred_path} nor {sar_mask_path} exists for {case_id}")
        img = Image.open(sar_mask_path).convert("L")
        mask = (np.array(img) > 127).astype(np.uint8)

    spill_coords = np.argwhere(mask == 1)  # (row, col)
    total_spill_pixels = len(spill_coords)
    if total_spill_pixels == 0:
        raise ValueError(f"No spill pixels found in mask for {case_id}")

    # 2. Separate into interior and boundary using morphological erosion
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(mask, kernel, iterations=1)
    boundary = mask - eroded

    interior_coords = np.argwhere(eroded == 1)
    boundary_coords = np.argwhere(boundary == 1)

    rng = np.random.default_rng(seed)

    target_interior = int(round(n_particles * interior_ratio))
    target_boundary = n_particles - target_interior

    if len(interior_coords) == 0:
        chosen_interior = np.empty((0, 2), dtype=int)
        target_boundary = n_particles
    else:
        n_int_sample = min(target_interior, len(interior_coords))
        chosen_interior = interior_coords[rng.choice(len(interior_coords), n_int_sample, replace=False)]

    if len(boundary_coords) == 0:
        chosen_boundary = np.empty((0, 2), dtype=int)
    else:
        n_bnd_sample = min(n_particles - len(chosen_interior), len(boundary_coords))
        chosen_boundary = boundary_coords[rng.choice(len(boundary_coords), n_bnd_sample, replace=False)]

    chosen = np.vstack([chosen_interior, chosen_boundary])
    if len(chosen) < n_particles:
        remaining = n_particles - len(chosen)
        extra = spill_coords[rng.choice(len(spill_coords), remaining, replace=True)]
        chosen = np.vstack([chosen, extra])

    # 3. Determine geographic center: prefer Module 2 geometry.json, fallback to config
    geom_path = DATA_PROCESSED / f"{case_id}_geometry.json"
    if geom_path.exists():
        geom_data = json.loads(geom_path.read_text())
        center_lat = geom_data["geometry"]["centroid_geo"]["latitude"]
        center_lon = geom_data["geometry"]["centroid_geo"]["longitude"]
    else:
        center_lat = CASES[case_id]["spill_center"]["lat"]
        center_lon = CASES[case_id]["spill_center"]["lon"]

    # Centroid of the mask in pixel coordinates
    c_row = float(spill_coords[:, 0].mean())
    c_col = float(spill_coords[:, 1].mean())

    # Map each chosen pixel to physical metric offset, then to (lat, lon)
    rows = chosen[:, 0]
    cols = chosen[:, 1]

    dy_meters = - (rows - c_row) * PIXEL_SCALE_M  # negative row = North
    dx_meters = (cols - c_col) * PIXEL_SCALE_M    # positive col = East

    m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(center_lat))

    seed_lats = center_lat + (dy_meters / M_PER_DEG_LAT)
    seed_lons = center_lon + (dx_meters / (m_per_deg_lon + 1e-12))

    meta = {
        "case_id": case_id,
        "center_geo": {"latitude": center_lat, "longitude": center_lon},
        "total_spill_pixels": total_spill_pixels,
        "pixel_scale_m": PIXEL_SCALE_M,
        "n_particles": len(chosen),
        "n_interior": len(chosen_interior),
        "n_boundary": len(chosen_boundary),
        "seed": seed,
    }

    return seed_lats, seed_lons, meta
