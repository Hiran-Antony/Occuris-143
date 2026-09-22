"""
Module 7 — Null/Background Baseline

Generates and evaluates a set of null hypotheses sampled uniformly from
the Module 4 probable origin zone. Compares physical match scores against
the candidate vessel's best hypothesis.

Why a baseline?
    Without one, a "high" match score is uninterpretable. If almost any
    source location within the origin zone produces a similar footprint, a
    high candidate score tells us nothing. The baseline lets us ask:
    "Does this vessel's counterfactual outperform generic feasible sources?"

Baseline design constraints:
    1. Same physics, same particle count, same ensemble treatment as candidates.
    2. Deterministic: fixed seed (separate from ensemble seed).
    3. Sampling is uniform within the origin-zone ellipse — not raw lat/lon
       rejection which biases sampling toward zone corners.
    4. Source label for all baseline samples: ORIGIN_ZONE_SAMPLE.
    5. The baseline must NOT know which vessel is the candidate.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from src.counterfactual.schemas import (
    BaselineStats,
    PhysicalMetrics,
    ReleaseLocation,
    ReleaseSource,
)


def _sample_ellipse_uniform(
    center_lat: float,
    center_lon: float,
    semi_major_km: float,
    semi_minor_km: float,
    angle_deg: float,
    n: int,
    rng: np.random.Generator,
) -> List[Tuple[float, float]]:
    """Sample n points uniformly inside a geodetic ellipse.

    Uses the rejection-free polar method: sample (r, θ) with r ~ sqrt(U[0,1])
    to achieve uniform areal density inside the unit circle, then scale and
    rotate to the ellipse.

    Returns list of (lat, lon) in degrees.
    """
    EARTH_KM = 6371.0
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    u = rng.uniform(0.0, 1.0, n)
    theta = rng.uniform(0.0, 2 * math.pi, n)
    # Uniform in ellipse area
    r = np.sqrt(u)
    x_unit = r * np.cos(theta)   # unit circle
    y_unit = r * np.sin(theta)

    # Scale to ellipse semi-axes (km)
    x_km = x_unit * semi_minor_km
    y_km = y_unit * semi_major_km

    # Rotate by ellipse orientation
    x_rot = cos_a * x_km - sin_a * y_km
    y_rot = sin_a * x_km + cos_a * y_km

    # Convert km offsets to degrees
    dlat = np.degrees(y_rot / EARTH_KM)
    dlon = np.degrees(x_rot / (EARTH_KM * math.cos(math.radians(center_lat)) + 1e-12))

    return list(zip(center_lat + dlat, center_lon + dlon))


def run_baseline(
    origin_zone: Dict[str, Any],
    sar_acquisition_time_iso: str,
    release_time_iso: str,
    observed_raster: np.ndarray,
    velocity_field,        # VelocityField — forward import avoided for circularity
    gt,                    # GeoTransform
    config: Dict[str, Any],
) -> BaselineStats:
    """Run null-hypothesis baseline simulations.

    For each of N sampled origin-zone locations, runs forward transport and
    computes physical match vs the observed SAR raster.

    Parameters
    ----------
    origin_zone:
        Dict with keys: center_lat, center_lon, semi_major_km, semi_minor_km,
        angle_deg (from Module 4 / CaseContextV1).
    sar_acquisition_time_iso:
        SAR observation time — transport terminates here.
    release_time_iso:
        Release time used for all baseline samples (same as best candidate
        release time for a fair comparison).
    observed_raster:
        Binary SAR mask raster on the shared GeoTransform grid.
    velocity_field:
        Loaded VelocityField instance.
    gt:
        GeoTransform instance (same as used for candidate).
    config:
        Loaded counterfactual.yaml config dict.

    Returns
    -------
    BaselineStats
    """
    from datetime import datetime, timezone
    from src.counterfactual.particle_initializer import seed_point_release
    from src.counterfactual.transport import forward_transport
    from src.counterfactual.rasterizer import particles_to_raster
    from src.counterfactual.metrics import compute_physical_metrics
    from src.counterfactual.uncertainty import generate_ensemble

    bl_cfg = config["baseline"]
    n_samples = bl_cfg["n_samples"]
    rng_seed = bl_cfg["random_seed"]
    p_cfg = config["particles"]
    t_cfg = config["transport"]
    u_cfg = config["uncertainty"]
    m_cfg = config["physical_match"]
    r_cfg = config["rasterization"]

    rng = np.random.default_rng(rng_seed)

    # Parse times
    fmt_parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    t_release = fmt_parse(release_time_iso)
    t_sar = fmt_parse(sar_acquisition_time_iso)
    duration_h = (t_sar - t_release).total_seconds() / 3600.0
    if duration_h <= 0:
        # Degenerate: return a zero-score baseline
        return BaselineStats(
            n_samples=0,
            median_score=0.0, p25_score=0.0, p75_score=0.0,
            p95_score=0.0, min_score=0.0, max_score=0.0,
        )

    # Ensemble configs — identical treatment as candidate
    ensemble = generate_ensemble(
        n_members=config["ensemble"]["members"],
        windage_perturbation_fraction=u_cfg["windage_perturbation_fraction"],
        current_perturbation_fraction=u_cfg["current_perturbation_fraction"],
        diffusion_scale=u_cfg["diffusion_scale"],
        base_seed=config["ensemble"]["random_seed"],
    )

    # Sample origin-zone locations
    locations = _sample_ellipse_uniform(
        center_lat=origin_zone["center_lat"],
        center_lon=origin_zone["center_lon"],
        semi_major_km=origin_zone.get("semi_major_km", 5.0),
        semi_minor_km=origin_zone.get("semi_minor_km", 5.0),
        angle_deg=origin_zone.get("angle_deg", 0.0),
        n=n_samples,
        rng=rng,
    )

    scores: List[float] = []
    lat_min = gt.lat_min; lat_max = gt.lat_max
    lon_min = gt.lon_min; lon_max = gt.lon_max

    for i, (blat, blon) in enumerate(locations):
        member_scores = []
        for em in ensemble:
            lats, lons = seed_point_release(
                release_lat=blat,
                release_lon=blon,
                n_particles=p_cfg["count"],
                initial_spread_m=p_cfg["initial_spread_m"],
                rng_seed=em.rng_seed + i * 1000,  # vary per sample
            )
            try:
                final_lats, final_lons, _ = forward_transport(
                    velocity_field=velocity_field,
                    seed_lats=lats,
                    seed_lons=lons,
                    duration_hours=duration_h,
                    dt_minutes=t_cfg["dt_minutes"],
                    diffusion_scale=em.diffusion_scale,
                    rng_seed=em.rng_seed + i * 1000,
                )
            except Exception:
                continue

            sim_raster = particles_to_raster(
                final_lats, final_lons, gt,
                occupancy_threshold=r_cfg["occupancy_threshold"],
            )
            metrics = compute_physical_metrics(
                observed=observed_raster,
                simulated=sim_raster,
                lat_min=lat_min, lat_max=lat_max,
                lon_min=lon_min, lon_max=lon_max,
                weights=m_cfg["weights"],
                centroid_decay_km=m_cfg["centroid_decay_km"],
                hausdorff_decay_km=m_cfg["hausdorff_decay_km"],
            )
            member_scores.append(metrics.composite_score)

        if member_scores:
            scores.append(float(np.mean(member_scores)))

    if not scores:
        return BaselineStats(
            n_samples=0, median_score=0.0, p25_score=0.0, p75_score=0.0,
            p95_score=0.0, min_score=0.0, max_score=0.0,
        )

    arr = np.array(scores)
    return BaselineStats(
        n_samples=len(arr),
        median_score=float(np.median(arr)),
        p25_score=float(np.percentile(arr, 25)),
        p75_score=float(np.percentile(arr, 75)),
        p95_score=float(np.percentile(arr, 95)),
        min_score=float(np.min(arr)),
        max_score=float(np.max(arr)),
    )
