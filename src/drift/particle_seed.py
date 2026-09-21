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
from geo_transform import GeoTransform

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

    # 3. Map pixels to geographic coordinates using the shared GeoTransform.
    #    This uses the spill_bbox geographic extents / image dimensions — NOT
    #    PIXEL_SCALE_M (the SAR sensor resolution), which would compress all
    #    50 particles into a ~2.5 km domain regardless of the real spill extent.
    gt = GeoTransform(case_id, image_h=mask.shape[0], image_w=mask.shape[1])
    rows = chosen[:, 0].astype(np.float64)
    cols = chosen[:, 1].astype(np.float64)
    seed_lats, seed_lons = gt.pixels_to_latlons(rows, cols)

    # Pre-seeding diagnostic (mandatory — validates spread before any drift)
    lat_span_km = (seed_lats.max() - seed_lats.min()) * 111.32
    lon_span_km = (seed_lons.max() - seed_lons.min()) * 111.32
    m_row, m_col = gt.metres_per_pixel()
    geo_w_km, geo_h_km = gt.summary()["geographic_width_km"], gt.summary()["geographic_height_km"]

    meta = {
        "case_id":           case_id,
        "center_geo":        {"latitude": float(seed_lats.mean()), "longitude": float(seed_lons.mean())},
        "total_spill_pixels": total_spill_pixels,
        "n_particles":       len(chosen),
        "n_interior":        len(chosen_interior),
        "n_boundary":        len(chosen_boundary),
        "seed":              seed,
        "transform":         gt.summary(),
        "pre_seed_validation": {
            "lat_span_km":   round(float(lat_span_km), 3),
            "lon_span_km":   round(float(lon_span_km), 3),
            "geographic_width_km":  geo_w_km,
            "geographic_height_km": geo_h_km,
            "m_per_px_lat":  round(m_row, 2),
            "m_per_px_lon":  round(m_col, 2),
            "particles_span_expected": (
                f"~{lat_span_km:.1f} km × ~{lon_span_km:.1f} km  "
                f"(geo extent = {geo_h_km} × {geo_w_km} km)"
            ),
            "pass": bool(lat_span_km > 0.5 and lon_span_km > 0.5),
            "note": (
                "PASS: particles distributed across spill geographic extent"
                if lat_span_km > 0.5
                else "FAIL: particle span too small — check GeoTransform bbox"
            ),
        },
    }

    return seed_lats, seed_lons, meta
