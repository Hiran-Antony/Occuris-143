"""
Module 7 — Shared Forward Transport Adapter

This file is intentionally a thin adapter over the Module 3 physics kernel.
It does NOT invent new physics.

Architecture (shared kernel):
    Module 3  ── backward=True  ──┐
                                   ├── RK45DriftEngine (Dormand-Prince)
    Module 7  ── backward=False ──┘      src/drift/rk4.py

The transport engine has zero knowledge of:
    - vessel identity
    - AIS records
    - candidate ranking
    - guilt or innocence

It only knows:
    - particle positions (lat, lon)
    - environmental velocity field
    - time direction (forward)
    - timestep and duration

Integration method:
    RK45 Dormand-Prince (5th order, 6 function evaluations per step).
    The class in src/drift/rk4.py is named RK45DriftEngine and genuinely
    implements the Dormand-Prince tableau — the name is accurate.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

from src.drift.rk4 import RK45DriftEngine
from src.drift.velocity_field import VelocityField


def forward_transport(
    velocity_field: VelocityField,
    seed_lats: np.ndarray,
    seed_lons: np.ndarray,
    duration_hours: float,
    dt_minutes: float,
    diffusion_scale: float = 1.0,
    rng_seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, List[Tuple[np.ndarray, np.ndarray]]]:
    """Transport particles forward in time using the Module 3 RK45 kernel.

    Parameters
    ----------
    velocity_field:
        Loaded VelocityField instance (same environmental data used by M3).
    seed_lats, seed_lons:
        Initial particle positions (degrees).
    duration_hours:
        How long to transport forward. Must be positive.
        The simulation MUST terminate at SAR acquisition time — the caller is
        responsible for computing duration as:
            duration_hours = (sar_time - release_time).total_seconds() / 3600
    dt_minutes:
        Integration timestep (read from config/counterfactual.yaml).
    diffusion_scale:
        Multiplier applied to Smagorinsky Kh before passing to the engine.
        Ensemble members vary this via uncertainty.py.
    rng_seed:
        Fixed seed — identical inputs always produce identical outputs.

    Returns
    -------
    final_lats, final_lons:
        Particle positions at end of transport (SAR acquisition time).
    trajectories:
        List of (lats, lons) snapshots at each timestep.
    """
    if duration_hours <= 0:
        raise ValueError(
            f"forward_transport requires duration_hours > 0, got {duration_hours:.2f}. "
            "Ensure release_time < sar_acquisition_time."
        )

    if diffusion_scale != 1.0:
        # Build a scaled diffusivity callable that applies the multiplier
        original_diff_func = velocity_field.get_eddy_diffusivity

        def scaled_diffusivity(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
            return original_diff_func(lats, lons) * diffusion_scale  # type: ignore[operator]

        engine = RK45DriftEngine(
            velocity_func=velocity_field.get_velocity,
            diffusivity_func=scaled_diffusivity,
        )
    else:
        engine = RK45DriftEngine(
            velocity_func=velocity_field.get_velocity,
            diffusivity_func=velocity_field.get_eddy_diffusivity,
        )

    # backward=False → forward integration (Module 7)
    final_lats, final_lons, trajectories = engine.integrate(
        seed_lats=seed_lats,
        seed_lons=seed_lons,
        duration_hours=duration_hours,
        dt_minutes=dt_minutes,
        backward=False,
        seed=rng_seed,
    )
    return final_lats, final_lons, trajectories
