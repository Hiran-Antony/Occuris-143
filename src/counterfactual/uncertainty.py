"""
Module 7 — Environmental Uncertainty / Ensemble Generation

Produces deterministic ensemble member configurations by perturbing
documented uncertainty parameters.

Separate uncertainty axes:
    1. Release-location uncertainty  — handled in particle_initializer.py
    2. Environmental uncertainty     — handled here
    3. Numerical uncertainty         — inherent to the RK45 integrator

These must NOT be double-counted.

Design rules:
    - Uses a fixed seed for reproducibility.
    - Only perturbs parameters that are explicitly declared in config.
    - Never uses raw random.random() — all randomness is seeded.
    - The identical ensemble treatment is applied to candidate AND baseline.

Environmental perturbation model:
    Windage is modelled as a fraction of wind speed (NOAA guidance).
    A ±windage_perturbation_fraction multiplier varies the coefficient.
    Same for current U, V components.

    For N ensemble members (including the "nominal" member at index 0):
        member 0: nominal (no perturbation)
        members 1..N-1: linearly spaced perturbation factors in [-frac, +frac]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass(frozen=True)
class EnsembleMemberConfig:
    """Configuration for a single ensemble member.

    Fields document exactly what was perturbed — traceable to config.
    """
    member_index: int
    windage_multiplier: float       # applied to VelocityField.wind_leeway_coeff
    current_multiplier: float       # applied to VelocityField curr_U / curr_V
    diffusion_scale: float          # applied in transport.forward_transport
    rng_seed: int                   # particle + diffusion seed for this member


def generate_ensemble(
    n_members: int,
    windage_perturbation_fraction: float,
    current_perturbation_fraction: float,
    diffusion_scale: float,
    base_seed: int,
) -> List[EnsembleMemberConfig]:
    """Generate N ensemble member configurations.

    Member 0 is always the nominal (unperturbed) run.
    Members 1..N-1 vary windage and current within ±fraction.

    Parameters
    ----------
    n_members:
        Total ensemble size (from config ensemble.members).
    windage_perturbation_fraction:
        Max fractional deviation for windage. E.g., 0.10 → ±10%.
    current_perturbation_fraction:
        Max fractional deviation for current U, V.
    diffusion_scale:
        Base Smagorinsky multiplier (all members share this for now).
    base_seed:
        Master seed (from config ensemble.random_seed).

    Returns
    -------
    List of EnsembleMemberConfig, length n_members.
    """
    configs: List[EnsembleMemberConfig] = []
    rng = np.random.default_rng(base_seed)

    if n_members < 1:
        raise ValueError("n_members must be >= 1.")

    # Member 0: nominal — no perturbation
    configs.append(
        EnsembleMemberConfig(
            member_index=0,
            windage_multiplier=1.0,
            current_multiplier=1.0,
            diffusion_scale=diffusion_scale,
            rng_seed=int(rng.integers(0, 2**31)),
        )
    )

    # Members 1..N-1: deterministic perturbations
    if n_members > 1:
        # Linearly spaced perturbation factors in [-frac, +frac], excluding 0
        w_factors = np.linspace(
            -windage_perturbation_fraction,
            +windage_perturbation_fraction,
            n_members - 1,
        )
        c_factors = np.linspace(
            -current_perturbation_fraction,
            +current_perturbation_fraction,
            n_members - 1,
        )
        for i, (wf, cf) in enumerate(zip(w_factors, c_factors), start=1):
            configs.append(
                EnsembleMemberConfig(
                    member_index=i,
                    windage_multiplier=float(np.clip(1.0 + wf, 0.0, 2.0)),
                    current_multiplier=float(np.clip(1.0 + cf, 0.0, 2.0)),
                    diffusion_scale=diffusion_scale,
                    rng_seed=int(rng.integers(0, 2**31)),
                )
            )

    return configs
