"""
Module 7 — Counterfactual Trajectory Reasoning Engine

Orchestrates the full pipeline:

    For each eligible candidate vessel (from Module 6):
        1. Build release hypotheses (release_sampler)
        2. For each hypothesis × ensemble member:
               a. Seed particles (particle_initializer)
               b. Forward transport to SAR time (transport)
               c. Rasterize (rasterizer)
               d. Compute metrics (metrics)
        3. Select best hypothesis per vessel
        4. Run null/background baseline (baseline)
        5. Run time sensitivity (sensitivity)
        6. Assemble evidence bundle (evidence_bundle)
        7. Run validation checks (validation)

Module 7 has zero knowledge of:
    - Which vessel is the "expected" answer
    - Ground truth
    - AIS anomaly scoring (that is Module 6)

It only evaluates: physical consistency of a hypothetical release.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import yaml

from src.ais.schemas import EvidenceBundleV1, Module6VerificationBundleV1, VesselTrack
from src.counterfactual.candidate_selector import select_candidates
from src.counterfactual.evidence_bundle import assemble_bundle
from src.counterfactual.particle_initializer import seed_point_release
from src.counterfactual.rasterizer import build_geotransform, load_sar_mask_raster, particles_to_raster
from src.counterfactual.release_sampler import ENVIRONMENT_VERSION, sample_hypotheses
from src.counterfactual.schemas import (
    BestHypothesisSummary,
    CounterfactualEvidenceBundleV1,
    EnsembleResult,
    PhysicalMetrics,
)
from src.counterfactual.transport import forward_transport
from src.counterfactual.uncertainty import generate_ensemble
from src.counterfactual.metrics import compute_physical_metrics
from src.counterfactual.validation import (
    assert_no_guilt_language,
    assert_score_bounds,
)
from src.config import ROOT


def load_counterfactual_config(path: Optional[Path] = None) -> Dict[str, Any]:
    cfg_path = path or (ROOT / "config" / "counterfactual.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _mean_metrics(metrics_list: List[PhysicalMetrics]) -> PhysicalMetrics:
    """Average PhysicalMetrics fields over a list of members."""
    if not metrics_list:
        raise ValueError("Cannot average empty metrics list.")
    fields = dataclasses.fields(metrics_list[0])
    averaged = {}
    for f in fields:
        vals = [getattr(m, f.name) for m in metrics_list]
        averaged[f.name] = float(np.mean(vals))
    return PhysicalMetrics(**averaged)


def _simulate_hypothesis(
    hyp,
    sar_acquisition_time_iso: str,
    observed_raster: np.ndarray,
    velocity_field,
    gt,
    ensemble,
    config: Dict[str, Any],
) -> Optional[EnsembleResult]:
    """Run all ensemble members for a single hypothesis. Returns None on failure."""
    t_release = _parse_dt(hyp.release_time_iso)
    t_sar = _parse_dt(sar_acquisition_time_iso)
    duration_h = (t_sar - t_release).total_seconds() / 3600.0

    if duration_h <= 0:
        return None

    p_cfg = config["particles"]
    t_cfg = config["transport"]
    r_cfg = config["rasterization"]
    m_cfg = config["physical_match"]
    lat_min = gt.lat_min; lat_max = gt.lat_max
    lon_min = gt.lon_min; lon_max = gt.lon_max
    H, W = gt.H, gt.W

    member_metrics: List[PhysicalMetrics] = []
    member_scores: List[float] = []

    for em in ensemble:
        lats, lons = seed_point_release(
            release_lat=hyp.release_location.lat,
            release_lon=hyp.release_location.lon,
            n_particles=p_cfg["count"],
            initial_spread_m=p_cfg["initial_spread_m"],
            rng_seed=em.rng_seed,
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
        member_metrics.append(metrics)
        member_scores.append(metrics.composite_score)

    if not member_scores:
        return None

    return EnsembleResult(
        hypothesis_id=hyp.hypothesis_id,
        member_scores=member_scores,
        mean_metrics=_mean_metrics(member_metrics),
    )


class CounterfactualEngine:
    """Module 7 orchestrator."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_counterfactual_config()

    def run_case(
        self,
        case_id: str,
        case_cfg: Dict[str, Any],
        m5_bundles: List[EvidenceBundleV1],
        m6_bundles: List[Module6VerificationBundleV1],
        tracks: Optional[Dict[str, VesselTrack]] = None,
        velocity_field=None,
    ) -> List[CounterfactualEvidenceBundleV1]:
        """Run Module 7 for all eligible vessels in a case.

        Parameters
        ----------
        case_cfg:
            Entry from src/config.py CASES dict.
        m5_bundles, m6_bundles:
            Module 5 and 6 outputs.
        tracks:
            Optional vessel track data keyed by vessel_id.
        velocity_field:
            Pre-loaded VelocityField. If None, one is created from config paths.
        """
        from src.drift.velocity_field import VelocityField

        cfg = self.config
        if velocity_field is None:
            velocity_field = VelocityField()

        # Build shared GeoTransform (same as Modules 2, 3, 4)
        gt = build_geotransform(case_cfg)

        # Load observed SAR mask
        mask_path = str(case_cfg["sar_mask"])
        observed_raster = load_sar_mask_raster(mask_path, gt)

        sar_time_iso = case_cfg["sar_timestamp"]
        t_sar = _parse_dt(sar_time_iso)
        release_window_hours = case_cfg.get("release_window_hours", 24)
        t_window_end = t_sar
        t_window_start = t_sar - __import__("datetime").timedelta(hours=release_window_hours)

        # Candidate selection
        candidates = select_candidates(m5_bundles, m6_bundles, tracks)

        # Build ensemble configs (same for all candidates — fair comparison)
        u_cfg = cfg["uncertainty"]
        ensemble = generate_ensemble(
            n_members=cfg["ensemble"]["members"],
            windage_perturbation_fraction=u_cfg["windage_perturbation_fraction"],
            current_perturbation_fraction=u_cfg["current_perturbation_fraction"],
            diffusion_scale=u_cfg["diffusion_scale"],
            base_seed=cfg["ensemble"]["random_seed"],
        )

        results: List[CounterfactualEvidenceBundleV1] = []

        for m5, m6, sel_record in candidates:
            if not sel_record.eligible or m6 is None:
                # Still emit a bundle so Module 8 has a complete picture
                bundle = assemble_bundle(
                    case_id=case_id,
                    vessel_id=sel_record.vessel_id,
                    selection_record=sel_record,
                    hypotheses_tested=0,
                    best_hypothesis=None,
                    baseline=None,
                    time_sensitivity=None,
                    environment_version=ENVIRONMENT_VERSION,
                )
                results.append(bundle)
                continue

            # Build vessel track points from Module 5 data
            track_points = _extract_track_points(m5, tracks)

            # Sample hypotheses
            hypotheses = sample_hypotheses(
                vessel_id=m5.vessel_id,
                release_window_start=t_window_start,
                release_window_end=t_window_end,
                time_step_hours=cfg["release"]["time_step_hours"],
                track_points=track_points,
                particle_count=cfg["particles"]["count"],
                ensemble_members=cfg["ensemble"]["members"],
            )

            if not hypotheses:
                bundle = assemble_bundle(
                    case_id=case_id,
                    vessel_id=m5.vessel_id,
                    selection_record=sel_record,
                    hypotheses_tested=0,
                    best_hypothesis=None,
                    baseline=None,
                    time_sensitivity=None,
                    environment_version=ENVIRONMENT_VERSION,
                )
                results.append(bundle)
                continue

            # Simulate all hypotheses
            best_result: Optional[EnsembleResult] = None
            best_hyp = None

            for hyp in hypotheses:
                result = _simulate_hypothesis(
                    hyp=hyp,
                    sar_acquisition_time_iso=sar_time_iso,
                    observed_raster=observed_raster,
                    velocity_field=velocity_field,
                    gt=gt,
                    ensemble=ensemble,
                    config=cfg,
                )
                if result is None:
                    continue
                if (best_result is None or
                        result.mean_metrics.composite_score >
                        best_result.mean_metrics.composite_score):
                    best_result = result
                    best_hyp = hyp

            # Baseline
            baseline_stats = None
            origin_zone = _extract_origin_zone(case_cfg)
            if origin_zone and best_hyp is not None:
                from src.counterfactual.baseline import run_baseline
                baseline_stats = run_baseline(
                    origin_zone=origin_zone,
                    sar_acquisition_time_iso=sar_time_iso,
                    release_time_iso=best_hyp.release_time_iso,
                    observed_raster=observed_raster,
                    velocity_field=velocity_field,
                    gt=gt,
                    config=cfg,
                )

            # Time sensitivity
            time_sens = None
            if best_hyp is not None and best_result is not None:
                from src.counterfactual.sensitivity import run_time_sensitivity
                time_sens = run_time_sensitivity(
                    best_release_time_iso=best_hyp.release_time_iso,
                    best_release_lat=best_hyp.release_location.lat,
                    best_release_lon=best_hyp.release_location.lon,
                    sar_acquisition_time_iso=sar_time_iso,
                    observed_raster=observed_raster,
                    velocity_field=velocity_field,
                    gt=gt,
                    config=cfg,
                )

            # Assemble best hypothesis summary
            best_summary = None
            if best_hyp is not None and best_result is not None:
                assert_score_bounds(best_result.mean_metrics.composite_score)
                best_summary = BestHypothesisSummary(
                    hypothesis_id=best_hyp.hypothesis_id,
                    release_time_iso=best_hyp.release_time_iso,
                    release_location=best_hyp.release_location,
                    release_mode=best_hyp.release_mode,
                    ensemble_member_count=len(best_result.member_scores),
                    physical_metrics=best_result.mean_metrics,
                )

            bundle = assemble_bundle(
                case_id=case_id,
                vessel_id=m5.vessel_id,
                selection_record=sel_record,
                hypotheses_tested=len(hypotheses),
                best_hypothesis=best_summary,
                baseline=baseline_stats,
                time_sensitivity=time_sens,
                environment_version=ENVIRONMENT_VERSION,
            )

            assert_no_guilt_language(bundle)
            results.append(bundle)

        return results


def _extract_track_points(
    m5: EvidenceBundleV1,
    tracks: Optional[Dict],
) -> list:
    """Extract a list of {timestamp, lat, lon, is_reconstructed} from M5 data."""
    points = []

    # Use journey milestones from the Evidence Bundle
    for milestone in getattr(m5, "journey_milestones", []) or []:
        ts = getattr(milestone, "timestamp", None)
        lat = getattr(milestone, "lat", None)
        lon = getattr(milestone, "lon", None)
        if ts and lat is not None and lon is not None:
            points.append({
                "timestamp": _parse_dt(str(ts)) if isinstance(ts, str) else ts,
                "lat": float(lat),
                "lon": float(lon),
                "is_reconstructed": False,
            })

    # Also include dark-path reconstructed positions from M5
    for hyp in getattr(m5, "dark_path_hypotheses", []) or []:
        for pt in getattr(hyp, "reconstructed_positions", []) or []:
            ts = getattr(pt, "timestamp", None)
            lat = getattr(pt, "lat", None)
            lon = getattr(pt, "lon", None)
            if ts and lat is not None and lon is not None:
                points.append({
                    "timestamp": _parse_dt(str(ts)) if isinstance(ts, str) else ts,
                    "lat": float(lat),
                    "lon": float(lon),
                    "is_reconstructed": True,
                })

    # Fallback: VesselTrack if provided
    if not points and tracks:
        vt = tracks.get(m5.vessel_id)
        if vt:
            for ping in getattr(vt, "pings", []) or []:
                ts = getattr(ping, "timestamp", None)
                lat = getattr(ping, "lat", None)
                lon = getattr(ping, "lon", None)
                if ts and lat is not None and lon is not None:
                    points.append({
                        "timestamp": _parse_dt(str(ts)) if isinstance(ts, str) else ts,
                        "lat": float(lat),
                        "lon": float(lon),
                        "is_reconstructed": False,
                    })

    return points


def _extract_origin_zone(case_cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract origin zone parameters from case config for baseline sampling."""
    bbox = case_cfg.get("spill_bbox")
    center = case_cfg.get("spill_center")
    if not bbox or not center:
        return None
    # Approximate ellipse from bounding box
    lat_span = (bbox["lat_max"] - bbox["lat_min"]) / 2.0
    lon_span = (bbox["lon_max"] - bbox["lon_min"]) / 2.0
    EARTH_KM = 6371.0
    import math
    semi_major_km = lat_span * (math.pi / 180.0) * EARTH_KM
    semi_minor_km = lon_span * (math.pi / 180.0) * EARTH_KM * math.cos(
        math.radians(center["lat"])
    )
    return {
        "center_lat": center["lat"],
        "center_lon": center["lon"],
        "semi_major_km": max(semi_major_km, 1.0),
        "semi_minor_km": max(semi_minor_km, 1.0),
        "angle_deg": 0.0,
    }
