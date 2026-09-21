"""
Module 3 — Backward Drift Forensics & Forward Dispersion Forecast (RK4 Engine)
Implements:
  1. Backward Hindcast to Reconstructed Discharge (-Xh)
  2. Forward Forecast to Impact Horizon (+48h)
  3. Continuous Timeline States with Plume Centroid, Area (km2), and Particle Plume
  4. Vector Hydrodynamics (HYCOM / GFS) matching operational marine surveillance displays
  5. Timeline Milestones: Reconstructed Discharge, S1 Scan, +12h, +24h, +48h

Output:
  - data/processed/{case_id}_drift.json
"""
import sys
import json
import argparse
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np

from config import (
    CASES, DATA_PROCESSED, N_PARTICLES, DRIFT_HOURS,
    FORECAST_HOURS, DRIFT_TIME_STEP_MIN, WIND_DRIFT_COEFFICIENT,
    STRATIFIED_INTERIOR_RATIO, EDDY_DIFFUSIVITY_M2S
)
from drift.velocity_field import VelocityField
from drift.rk4 import RK45DriftEngine
from drift.particle_seed import sample_stratified_seed_points
from drift.origin_zone import (
    fit_origin_ellipse, compute_release_window, compute_plume_stats
)
from drift.weathering import compute_adios_weathering, compute_oceanographic_regime
from drift.schemas import (
    SimulationConfig, TimestepState, TimelineMilestone,
    TimelineRange, DriftResult
)


def format_utc_display(dt: datetime.datetime) -> str:
    """Formats datetime to 'Tue, 16 Jan 2024 05:10:00 UTC'."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S UTC")


def run_drift_case(
    case_id: str,
    vel_field: Optional[VelocityField] = None,
    hindcast_hours: Optional[float] = None,
    forecast_hours: Optional[float] = None,
    dt_minutes: float = DRIFT_TIME_STEP_MIN,
    eddy_diffusivity: float = EDDY_DIFFUSIVITY_M2S
) -> DriftResult:
    """
    Executes the full hindcast + forecast drift simulation for a single case.
    """
    case_meta = CASES[case_id]
    field = vel_field or VelocityField()

    h_hours = float(hindcast_hours if hindcast_hours is not None else case_meta.get("release_window_hours", DRIFT_HOURS))
    f_hours = float(forecast_hours if forecast_hours is not None else FORECAST_HOURS)

    # 1. Stratified particle seeding from SAR spill mask (70% interior, 30% boundary)
    seed_lats, seed_lons, seed_meta = sample_stratified_seed_points(
        case_id=case_id,
        n_particles=N_PARTICLES,
        interior_ratio=STRATIFIED_INTERIOR_RATIO,
        seed=42
    )

    # 2. Physics engine: RK45 Advanced Drift Engine
    vf = field
    engine = RK45DriftEngine(
        velocity_func=vf.get_velocity,
        diffusivity_func=vf.get_eddy_diffusivity
    )

    # 3. Simulate continuous timeline (-hindcast_hours -> 0h -> +forecast_hours)
    raw_states = engine.simulate_full_timeline(
        seed_lats=seed_lats,
        seed_lons=seed_lons,
        hindcast_hours=h_hours,
        forecast_hours=f_hours,
        dt_minutes=dt_minutes,
        seed=42
    )

    # Parse SAR observation timestamp
    sar_ts_clean = case_meta["sar_timestamp"].replace("Z", "+00:00")
    sar_dt = datetime.datetime.fromisoformat(sar_ts_clean)

    # 4. Process each timeline step: calculate plume centroid, area (km2), and hydrodynamics
    trajectory_states: List[TimestepState] = []
    milestone_candidates: Dict[str, Any] = {}

    for idx, raw in enumerate(raw_states):
        offset_hr = raw["time_offset_hours"]
        step_dt = sar_dt + datetime.timedelta(hours=offset_hr)
        lats = raw["lats"]
        lons = raw["lons"]

        c_lat, c_lon, area_km2 = compute_plume_stats(lats, lons)
        particles_list = [
            [round(float(la), 5), round(float(lo), 5)]
            for la, lo in zip(lats, lons)
        ]

        # Calculate localized hydrodynamics at the plume centroid
        hydro = field.get_vector_hydrodynamics(c_lat, c_lon)

        ts_state = TimestepState(
            step_index=idx,
            phase=raw["phase"],
            time_offset_hours=offset_hr,
            timestamp=step_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            formatted_time=format_utc_display(step_dt),
            plume_centroid={"latitude": c_lat, "longitude": c_lon},
            plume_area_km2=area_km2,
            particles=particles_list,
            vector_hydrodynamics=hydro,
            weathering=compute_adios_weathering(offset_hr, area_km2, hydro.wind_leeway.speed_knots)
        )
        trajectory_states.append(ts_state)

        # Record milestone steps
        if idx == 0:
            milestone_candidates["discharge"] = ts_state
        elif raw["phase"] == "observation" and offset_hr == 0.0:
            milestone_candidates["s1_scan"] = ts_state
        elif abs(offset_hr - 12.0) < (dt_minutes / 120.0):
            milestone_candidates["forecast_12h"] = ts_state
        elif abs(offset_hr - 24.0) < (dt_minutes / 120.0):
            milestone_candidates["forecast_24h"] = ts_state
        elif abs(offset_hr - f_hours) < (dt_minutes / 120.0):
            milestone_candidates["forecast_48h"] = ts_state

    # 5. Extract Origin Zone (at discharge step) & Release Window
    discharge_state = milestone_candidates.get("discharge", trajectory_states[0])
    origin_lats = np.array([p[0] for p in discharge_state.particles])
    origin_lons = np.array([p[1] for p in discharge_state.particles])

    origin_zone = fit_origin_ellipse(origin_lats, origin_lons)
    release_window = compute_release_window(
        sar_timestamp=case_meta["sar_timestamp"],
        drift_hours=h_hours,
        buffer_hours=2.0
    )

    # 6. Assemble Timeline Milestones
    s1_state = milestone_candidates.get("s1_scan", trajectory_states[len(trajectory_states)//2])
    f12_state = milestone_candidates.get("forecast_12h", s1_state)
    f24_state = milestone_candidates.get("forecast_24h", s1_state)
    f48_state = milestone_candidates.get("forecast_48h", trajectory_states[-1])

    milestones = [
        TimelineMilestone(
            id="reconstructed_discharge",
            label=f"-{int(h_hours)}h Reconstructed Discharge",
            time_offset_hours=-h_hours,
            timestamp=discharge_state.timestamp,
            formatted_time=discharge_state.formatted_time,
            plume_centroid=discharge_state.plume_centroid,
            plume_area_km2=discharge_state.plume_area_km2
        ),
        TimelineMilestone(
            id="s1_scan",
            label="0h S1 Scan",
            time_offset_hours=0.0,
            timestamp=s1_state.timestamp,
            formatted_time=s1_state.formatted_time,
            plume_centroid=s1_state.plume_centroid,
            plume_area_km2=s1_state.plume_area_km2
        ),
        TimelineMilestone(
            id="forecast_12h",
            label="+12h Forecast",
            time_offset_hours=12.0,
            timestamp=f12_state.timestamp,
            formatted_time=f12_state.formatted_time,
            plume_centroid=f12_state.plume_centroid,
            plume_area_km2=f12_state.plume_area_km2
        ),
        TimelineMilestone(
            id="forecast_24h",
            label="+24h Forecast",
            time_offset_hours=24.0,
            timestamp=f24_state.timestamp,
            formatted_time=f24_state.formatted_time,
            plume_centroid=f24_state.plume_centroid,
            plume_area_km2=f24_state.plume_area_km2
        ),
        TimelineMilestone(
            id="forecast_48h",
            label=f"+{int(f_hours)}h Impact Horizon",
            time_offset_hours=f_hours,
            timestamp=f48_state.timestamp,
            formatted_time=f48_state.formatted_time,
            plume_centroid=f48_state.plume_centroid,
            plume_area_km2=f48_state.plume_area_km2
        ),
    ]

    # 7. Local Vector Hydrodynamics at SAR Observation Centroid
    obs_hydro = field.get_vector_hydrodynamics(
        s1_state.plume_centroid["latitude"],
        s1_state.plume_centroid["longitude"]
    )

    # 8. Assemble full DriftResult
    timeline_range = TimelineRange(
        min_offset_hours=-h_hours,
        max_offset_hours=f_hours,
        total_steps=len(trajectory_states)
    )
    
    regime = compute_oceanographic_regime(s1_state.plume_centroid["latitude"], s1_state.plume_centroid["longitude"])

    result = DriftResult(
        case_id=case_id,
        sar_timestamp=case_meta["sar_timestamp"],
        simulation=SimulationConfig(
            hindcast_hours=int(h_hours),
            forecast_hours=int(f_hours),
            time_step_minutes=dt_minutes,
            particle_count=N_PARTICLES,
            engine="RK45",
            eddy_diffusivity_m2s=eddy_diffusivity
        ),
        vector_hydrodynamics=obs_hydro,
        oceanographic_regime=regime,
        milestones=milestones,
        origin_zone=origin_zone,
        release_time_window=release_window,
        timeline_range=timeline_range,
        trajectory=trajectory_states,
        preview_plot=None
    )

    # 9. Save JSON artifact
    json_path = DATA_PROCESSED / f"{case_id}_drift.json"
    json_dict = result.to_dict()
    # Add top-level convenience coordinates for downstream modules (Module 4 SpillSplit, Module 7)
    json_dict["origin_lats"] = [round(float(x), 5) for x in origin_lats]
    json_dict["origin_lons"] = [round(float(x), 5) for x in origin_lons]
    json_path.write_text(json.dumps(json_dict, indent=2))

    return result


def main(case_ids: Optional[List[str]] = None):
    print("\n" + "=" * 66)
    print("Module 3 -- Drift Forensics & Forecast Engine (RK4 + Hydrodynamics)")
    print("=" * 66)

    field = VelocityField()
    target_cases = case_ids or list(CASES.keys())

    for cid in target_cases:
        print(f"\n[RUNNING] {cid} ({CASES[cid]['title']})")
        res = run_drift_case(cid, vel_field=field)
        oz = res.origin_zone
        rw = res.release_time_window
        vh = res.vector_hydrodynamics
        sc = vh.surface_current
        wl = vh.wind_leeway
        na = vh.net_advection

        print(f"  Timeline Range   : {res.timeline_range.min_offset_hours:.1f}h to +{res.timeline_range.max_offset_hours:.1f}h ({res.timeline_range.total_steps} steps)")
        print(f"  Hydrodynamics    : [{vh.model_source}]")
        print(f"    Surface Current: {sc.speed_mps:.2f} m/s @ {sc.direction_deg:.0f} deg")
        print(f"    Wind Leeway    : {wl.speed_knots:.1f} kts @ {wl.direction_deg:.0f} deg")
        print(f"    Net Advection  : {na.speed_kmh:.2f} km/h ({na.speed_knots:.2f} kts) @ {na.direction_deg:.0f} deg")
        print(f"  Milestones:")
        for m in res.milestones:
            c = m.plume_centroid
            print(f"    * {m.label:<28}: {m.formatted_time} | Centroid: {c['latitude']:.4f} N, {c['longitude']:.4f} E | Area: {m.plume_area_km2:.2f} km2")
        print(f"  Origin 2-sigma   : a={oz.semi_major_km:.2f} km, b={oz.semi_minor_km:.2f} km, Area={oz.area_km2:.2f} km2")
        print(f"  Release Window   : {rw.release_start} -> {rw.release_end} ({rw.window_hours}h window)")
        print(f"  Saved JSON       : data/processed/{cid}_drift.json")

    print("\n" + "=" * 66)
    print(f"[OK] Module 3 Definition of Done: Reconstructed origin zones and forecast trajectories for {len(target_cases)} cases.")
    print("=" * 66 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Occuris Module 3 — Drift Forensics & Forecast")
    parser.add_argument("--case", type=str, default=None, help="Target case ID (e.g. case_01)")
    args = parser.parse_args()

    selected = [args.case] if args.case else None
    main(case_ids=selected)
