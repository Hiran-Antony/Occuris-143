"""
Module 7 — Particle Initializer

Seeds oil particles at a hypothetical release point.

For POINT release mode:
    All N particles are placed at the release location with a documented
    Gaussian positional spread (initial_spread_m) representing release
    location uncertainty.

    This same spread is applied to EVERY simulation — candidate and baseline —
    so the uncertainty treatment is identical and comparisons remain fair.

Design constraint:
    The spread is controlled by config/counterfactual.yaml:particles.initial_spread_m
    and must NOT be tuned to improve any specific candidate's match score.

Coordinate convention:
    Gaussian spread is applied in metric (East, North) space, then converted
    back to lat/lon using the same geo ↔ metric transforms from src/drift/rk4.py.
    This avoids degree-level artefacts near the equator.
"""

from __future__ import annotations

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def _metric_offset_to_latlon(
    dlat_m: np.ndarray,
    dlon_m: np.ndarray,
    lat0: float,
    lon0: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert metric offsets (m) from an origin to lat/lon offsets (deg)."""
    dlat_deg = np.degrees(dlat_m / EARTH_RADIUS_M)
    dlon_deg = np.degrees(dlon_m / (EARTH_RADIUS_M * np.cos(np.radians(lat0)) + 1e-12))
    return lat0 + dlat_deg, lon0 + dlon_deg


def seed_point_release(
    release_lat: float,
    release_lon: float,
    n_particles: int,
    initial_spread_m: float,
    rng_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Seed N particles at (release_lat, release_lon) with Gaussian spread.

    Parameters
    ----------
    release_lat, release_lon:
        Release point (degrees). Must be inside the model domain.
    n_particles:
        Number of particles (from config particles.count).
    initial_spread_m:
        1-sigma Gaussian spread in metres (config particles.initial_spread_m).
        Applied identically to ALL simulations — candidate and baseline.
    rng_seed:
        Fixed RNG seed — identical inputs → identical particle arrays.

    Returns
    -------
    lats, lons : np.ndarray, shape (n_particles,)
    """
    rng = np.random.default_rng(rng_seed)
    # Sample offsets in metric space
    dlon_m = rng.normal(0.0, initial_spread_m, n_particles)
    dlat_m = rng.normal(0.0, initial_spread_m, n_particles)
    lats, lons = _metric_offset_to_latlon(dlat_m, dlon_m, release_lat, release_lon)
    return lats, lons
