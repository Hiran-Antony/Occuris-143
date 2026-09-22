"""
Module 7 — Rasterizer

Converts particle clouds and SAR masks to a common geographic binary raster
so that physical comparison metrics operate on like-for-like representations.

Critical design rule (from architecture review):
    The observed SAR mask and the simulated particle cloud MUST be rasterized
    to the *same* CRS, extent, and resolution before IoU or any other metric
    is calculated. Using different grids will produce silently wrong scores.

This module uses the GeoTransform from src/geo_transform.py — the same
coordinate mapping used by Modules 2, 3, and 4. This is not optional.

Rasterization method — grid occupancy:
    A cell is "occupied" if the particle count in that cell >= occupancy_threshold.
    The threshold is read from config/counterfactual.yaml.
    It must be identical for candidate and baseline simulations.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
from PIL import Image

from src.geo_transform import GeoTransform


def build_geotransform(case_cfg: Dict[str, Any]) -> GeoTransform:
    """Build the shared GeoTransform from a case config dict.

    Delegates to the canonical GeoTransform(case_id) constructor so that
    Module 7 uses the same transform as Modules 2, 3, and 4.
    """
    return GeoTransform(case_cfg["id"])


def _gt_dims(gt: GeoTransform):
    """Return (height, width) — works with GeoTransform attribute names H and W."""
    return gt.H, gt.W


def _gt_extents(gt: GeoTransform):
    """Return (lat_min, lat_max, lon_min, lon_max)."""
    return gt.lat_min, gt.lat_max, gt.lon_min, gt.lon_max


def load_sar_mask_raster(mask_path: str, gt: GeoTransform) -> np.ndarray:
    """Load a SAR binary mask PNG and resize to the GeoTransform grid dimensions.

    Returns
    -------
    ndarray, shape (H, W), dtype bool
        True where the mask indicates a spill pixel.
    """
    H, W = _gt_dims(gt)
    img = Image.open(mask_path).convert("L")
    img = img.resize((W, H), Image.NEAREST)
    arr = np.array(img, dtype=np.float32)
    return arr > 0


def particles_to_raster(
    lats: np.ndarray,
    lons: np.ndarray,
    gt: GeoTransform,
    occupancy_threshold: int,
) -> np.ndarray:
    """Convert a particle cloud to a binary occupancy raster.

    Particles outside the GeoTransform extent are silently clipped (they
    have drifted out of the scene and contribute no information).

    Parameters
    ----------
    lats, lons:
        Particle positions (degrees). Shape (n_particles,).
    gt:
        GeoTransform defining the canonical grid (same as observed mask).
    occupancy_threshold:
        Integer; cells with >= this many particles are marked occupied.
        Read from config — never adjusted to favour a specific hypothesis.

    Returns
    -------
    ndarray, shape (H, W), dtype bool
    """
    H, W = _gt_dims(gt)
    counts = np.zeros((H, W), dtype=np.int32)

    for lat, lon in zip(lats, lons):
        # latlon_to_pixel returns (row, col) in GeoTransform convention
        row, col = gt.latlon_to_pixel(lat, lon)
        row_i, col_i = int(row), int(col)
        if 0 <= row_i < H and 0 <= col_i < W:
            counts[row_i, col_i] += 1

    return counts >= occupancy_threshold
