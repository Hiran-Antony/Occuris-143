"""
Module 7 — Time Sensitivity Analysis

For the best-scoring hypothesis of a candidate vessel, re-runs the simulation
at a set of time offsets (e.g., ±6h, ±12h relative to the best release time).

Purpose:
    Tests whether the physical match is specifically associated with the
    estimated release window, rather than merely with the vessel being
    somewhere nearby.

Interpretation:
    - If the score peaks near offset 0, that supports the estimated window.
    - If the score peaks at, say, -6h, that is recorded honestly as
      best_offset_hours = -6 — it is NOT masked or suppressed.
    - The full score dict is included in the output bundle for transparency.

Design constraint:
    Same physics, particle count, and ensemble treatment as all other
    simulations. No special tuning for any vessel.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import numpy as np

from src.counterfactual.schemas import TimeSensitivity


def run_time_sensitivity(
    best_release_time_iso: str,
    best_release_lat: float,
    best_release_lon: float,
    sar_acquisition_time_iso: str,
    observed_raster: np.ndarray,
    velocity_field,
    gt,
    config: Dict[str, Any],
) -> TimeSensitivity:
    """Re-simulate at each configured time offset from the best release time.

    Parameters
    ----------
    best_release_time_iso:
        ISO-8601 UTC timestamp of the best-scoring hypothesis.
    best_release_lat, best_release_lon:
        Release location of the best-scoring hypothesis.
    sar_acquisition_time_iso:
        SAR observation time — transport always terminates here.
    observed_raster:
        Binary SAR mask on the shared GeoTransform grid.
    velocity_field, gt:
        Same instances used for candidate simulation.
    config:
        Loaded counterfactual.yaml.

    Returns
    -------
    TimeSensitivity dataclass.
    """
    from src.counterfactual.particle_initializer import seed_point_release
    from src.counterfactual.transport import forward_transport
    from src.counterfactual.rasterizer import particles_to_raster
    from src.counterfactual.metrics import compute_physical_metrics
    from src.counterfactual.uncertainty import generate_ensemble

    fmt_parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    t_best = fmt_parse(best_release_time_iso)
    t_sar = fmt_parse(sar_acquisition_time_iso)

    offsets: List[float] = config["time_sensitivity"]["offsets_hours"]
    p_cfg = config["particles"]
    t_cfg = config["transport"]
    u_cfg = config["uncertainty"]
    m_cfg = config["physical_match"]
    r_cfg = config["rasterization"]
    lat_min = gt.lat_min; lat_max = gt.lat_max
    lon_min = gt.lon_min; lon_max = gt.lon_max

    ensemble = generate_ensemble(
        n_members=config["ensemble"]["members"],
        windage_perturbation_fraction=u_cfg["windage_perturbation_fraction"],
        current_perturbation_fraction=u_cfg["current_perturbation_fraction"],
        diffusion_scale=u_cfg["diffusion_scale"],
        base_seed=config["ensemble"]["random_seed"],
    )

    scores: Dict[float, float] = {}

    for offset_h in offsets:
        t_release = t_best + timedelta(hours=offset_h)
        duration_h = (t_sar - t_release).total_seconds() / 3600.0

        if duration_h <= 0:
            scores[float(offset_h)] = 0.0
            continue

        member_scores = []
        for em in ensemble:
            lats, lons = seed_point_release(
                release_lat=best_release_lat,
                release_lon=best_release_lon,
                n_particles=p_cfg["count"],
                initial_spread_m=p_cfg["initial_spread_m"],
                rng_seed=em.rng_seed + int(abs(offset_h) * 100),
            )
            try:
                final_lats, final_lons, _ = forward_transport(
                    velocity_field=velocity_field,
                    seed_lats=lats, seed_lons=lons,
                    duration_hours=duration_h,
                    dt_minutes=t_cfg["dt_minutes"],
                    diffusion_scale=em.diffusion_scale,
                    rng_seed=em.rng_seed,
                )
            except Exception:
                continue

            sim_raster = particles_to_raster(
                final_lats, final_lons, gt,
                occupancy_threshold=r_cfg["occupancy_threshold"],
            )
            metrics = compute_physical_metrics(
                observed=observed_raster, simulated=sim_raster,
                lat_min=lat_min, lat_max=lat_max,
                lon_min=lon_min, lon_max=lon_max,
                weights=m_cfg["weights"],
                centroid_decay_km=m_cfg["centroid_decay_km"],
                hausdorff_decay_km=m_cfg["hausdorff_decay_km"],
            )
            member_scores.append(metrics.composite_score)

        scores[float(offset_h)] = float(np.mean(member_scores)) if member_scores else 0.0

    # Report the offset with the highest score — even if it is not 0
    best_offset = max(scores, key=lambda k: scores[k])
    return TimeSensitivity(
        offsets_hours=list(offsets),
        scores=scores,
        best_offset_hours=float(best_offset),
    )
