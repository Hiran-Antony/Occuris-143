"""
Module 7 — Physical Comparison Metrics

Compares a simulated spill raster with the observed SAR spill mask using
five complementary spatial metrics. All metrics return values in [0, 1]
(higher = better agreement).

Metric definitions
------------------
1. IoU (Intersection over Union)
   |A ∩ B| / |A ∪ B|
   Measures spatial overlap.

2. Centroid Similarity
   exp(-d / D),  D = centroid_decay_km (from config)
   Exponential decay avoids the arbitrary 1/(1+d) normalization.
   The scale D is explicit and calibrated.

3. Area Similarity
   1 - |As - Ao| / max(As, Ao)
   Zero-area edge cases handled explicitly.

4. Shape Similarity (symmetric Hausdorff distance)
   exp(-H_sym / H_decay),  H_decay = hausdorff_decay_km
   Uses the symmetric Hausdorff: max(directed_A→B, directed_B→A).

5. Orientation Similarity (axial PCA angle)
   Fixes the axis vs arrow problem:
       Δθ_axial = min(|θ1 - θ2|, 180° - |θ1 - θ2|)
       S = 1 - Δθ_axial / 90°
   So 0° == 180° axis → similarity 1; perpendicular → similarity 0.

Composite score
   Weighted sum per config weights (weights must sum to 1).

All characteristic distances come from config — not hardcoded.
"""

from __future__ import annotations

import math
from typing import Dict

import numpy as np

from src.counterfactual.schemas import PhysicalMetrics

EARTH_RADIUS_KM = 6_371.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _raster_pixel_area_km2(lat_min: float, lat_max: float,
                             lon_min: float, lon_max: float,
                             height: int, width: int) -> float:
    """Approximate area of a single raster cell in km²."""
    dlat_km = (lat_max - lat_min) / height * (math.pi / 180.0) * EARTH_RADIUS_KM
    centre_lat = (lat_min + lat_max) / 2.0
    dlon_km = (lon_max - lon_min) / width * (math.pi / 180.0) * EARTH_RADIUS_KM * math.cos(
        math.radians(centre_lat)
    )
    return dlat_km * dlon_km


def _raster_centroid_latlon(
    mask: np.ndarray,
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
) -> tuple[float, float]:
    """Compute centroid (lat, lon) from a binary raster."""
    rows, cols = np.where(mask)
    if len(rows) == 0:
        centre_lat = (lat_min + lat_max) / 2.0
        centre_lon = (lon_min + lon_max) / 2.0
        return centre_lat, centre_lon
    h, w = mask.shape
    lat_res = (lat_max - lat_min) / h
    lon_res = (lon_max - lon_min) / w
    # Row 0 = top (max lat); row h-1 = bottom (min lat)
    lats = lat_max - (rows + 0.5) * lat_res
    lons = lon_min + (cols + 0.5) * lon_res
    return float(np.mean(lats)), float(np.mean(lons))


def _hausdorff_distance_km(
    obs: np.ndarray,
    sim: np.ndarray,
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
) -> float:
    """Symmetric Hausdorff distance in km between two binary masks.

    Uses pixel-level sampling — accurate enough for the grid resolution used.
    Returns 0 if either mask is empty (a degenerate case, noted in metrics).
    """
    h, w = obs.shape
    lat_res = (lat_max - lat_min) / h
    lon_res = (lon_max - lon_min) / w

    def boundary_points(mask: np.ndarray):
        rows, cols = np.where(mask)
        if len(rows) == 0:
            return None
        lats = lat_max - (rows + 0.5) * lat_res
        lons = lon_min + (cols + 0.5) * lon_res
        return np.stack([lats, lons], axis=1)  # (N, 2)

    A = boundary_points(obs)
    B = boundary_points(sim)

    if A is None or B is None:
        return 0.0

    def directed_hausdorff(X: np.ndarray, Y: np.ndarray) -> float:
        """max over x in X of min distance to any y in Y."""
        # Vectorized: (|X|, 1, 2) - (1, |Y|, 2) → (|X|, |Y|, 2)
        diff = X[:, np.newaxis, :] - Y[np.newaxis, :, :]
        # Approx Euclidean in degree space weighted by cos(lat)
        mid_lat = np.radians((lat_min + lat_max) / 2.0)
        diff_km = diff * np.array(
            [math.pi / 180.0 * EARTH_RADIUS_KM,
             math.pi / 180.0 * EARTH_RADIUS_KM * math.cos(mid_lat)]
        )
        dists = np.sqrt(np.sum(diff_km ** 2, axis=2))  # (|X|, |Y|)
        return float(np.max(np.min(dists, axis=1)))

    return max(directed_hausdorff(A, B), directed_hausdorff(B, A))


def _pca_orientation_deg(mask: np.ndarray) -> float:
    """PCA major-axis orientation in degrees [0, 180).

    Returns 0 if the mask has fewer than 2 occupied pixels.
    """
    rows, cols = np.where(mask)
    if len(rows) < 2:
        return 0.0
    pts = np.stack([rows.astype(float), cols.astype(float)], axis=1)
    pts -= pts.mean(axis=0)
    cov = np.cov(pts.T)
    if cov.ndim < 2:
        return 0.0
    eigvals, eigvecs = np.linalg.eigh(cov)
    major = eigvecs[:, np.argmax(eigvals)]
    angle = math.degrees(math.atan2(major[1], major[0])) % 180.0
    return angle


# ── Main metric computation ───────────────────────────────────────────────────

def compute_physical_metrics(
    observed: np.ndarray,
    simulated: np.ndarray,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    weights: Dict[str, float],
    centroid_decay_km: float,
    hausdorff_decay_km: float,
) -> PhysicalMetrics:
    """Compute all five physical comparison metrics.

    Parameters
    ----------
    observed:
        Binary raster from the SAR spill mask. dtype bool.
    simulated:
        Binary raster from particle occupancy. dtype bool.
    lat_min, lat_max, lon_min, lon_max:
        Geographic extent of BOTH rasters (they share the same grid).
    weights:
        Dict with keys 'iou', 'centroid', 'area', 'shape', 'orientation'.
        Must sum to 1. Read from config.
    centroid_decay_km:
        Characteristic decay distance for centroid similarity.
    hausdorff_decay_km:
        Characteristic length for Hausdorff normalisation.

    Returns
    -------
    PhysicalMetrics dataclass.
    """
    h, w = observed.shape
    cell_area_km2 = _raster_pixel_area_km2(lat_min, lat_max, lon_min, lon_max, h, w)

    # ── IoU ───────────────────────────────────────────────────────────────────
    intersection = float(np.sum(observed & simulated))
    union = float(np.sum(observed | simulated))
    iou = intersection / union if union > 0.0 else 0.0

    # ── Centroids ─────────────────────────────────────────────────────────────
    obs_clat, obs_clon = _raster_centroid_latlon(observed, lat_min, lat_max, lon_min, lon_max)
    sim_clat, sim_clon = _raster_centroid_latlon(simulated, lat_min, lat_max, lon_min, lon_max)
    centroid_dist_km = _haversine_km(obs_clat, obs_clon, sim_clat, sim_clon)
    centroid_sim = math.exp(-centroid_dist_km / centroid_decay_km)

    # ── Area ──────────────────────────────────────────────────────────────────
    obs_area = float(np.sum(observed)) * cell_area_km2
    sim_area = float(np.sum(simulated)) * cell_area_km2
    if max(obs_area, sim_area) > 0.0:
        area_sim = 1.0 - abs(sim_area - obs_area) / max(obs_area, sim_area)
    elif obs_area == 0.0 and sim_area == 0.0:
        # Both empty — degenerate, treat as perfect "agreement"
        area_sim = 1.0
    else:
        # One is zero, the other is not → worst disagreement
        area_sim = 0.0

    # ── Shape / Hausdorff ─────────────────────────────────────────────────────
    h_dist = _hausdorff_distance_km(
        observed, simulated, lat_min, lat_max, lon_min, lon_max
    )
    shape_sim = math.exp(-h_dist / hausdorff_decay_km)

    # ── Orientation (axial PCA) ────────────────────────────────────────────────
    obs_orient = _pca_orientation_deg(observed)
    sim_orient = _pca_orientation_deg(simulated)
    raw_diff = abs(obs_orient - sim_orient)
    # Axial correction: 0° and 180° represent the same axis
    axial_diff = min(raw_diff, 180.0 - raw_diff)
    orient_sim = 1.0 - axial_diff / 90.0

    # ── Composite weighted score ───────────────────────────────────────────────
    w = weights
    composite = (
        w["iou"] * iou
        + w["centroid"] * centroid_sim
        + w["area"] * area_sim
        + w["shape"] * shape_sim
        + w["orientation"] * orient_sim
    )
    # Clamp to [0, 1] to guard against floating-point edge cases
    composite = float(np.clip(composite, 0.0, 1.0))

    return PhysicalMetrics(
        iou=round(iou, 6),
        centroid_similarity=round(centroid_sim, 6),
        area_similarity=round(area_sim, 6),
        shape_similarity=round(shape_sim, 6),
        orientation_similarity=round(orient_sim, 6),
        composite_score=round(composite, 6),
        observed_area_km2=round(obs_area, 4),
        simulated_area_km2=round(sim_area, 4),
        centroid_distance_km=round(centroid_dist_km, 4),
        hausdorff_distance_km=round(h_dist, 4),
        orientation_delta_deg=round(axial_diff, 2),
    )
