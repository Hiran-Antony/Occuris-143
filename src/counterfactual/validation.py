"""
Module 7 — Validation Module

Physics and coordinate sanity checks run before and after simulation.
These tests are separate from pytest — they are runtime assertions that
validate the numerical and spatial behaviour of the transport kernel.

All checks must pass before the engine emits a result.
"""

from __future__ import annotations

import math
from typing import Tuple

import numpy as np


def assert_zero_velocity_stationary(
    velocity_field,
    seed_lat: float,
    seed_lon: float,
    duration_hours: float = 1.0,
    dt_minutes: float = 10.0,
    tolerance_m: float = 50.0,
) -> None:
    """Physics sanity: zero velocity → particles stay at release point.

    Creates a mock zero-velocity field and verifies particles don't move
    more than tolerance_m after duration_hours of forward transport.
    """
    from src.counterfactual.particle_initializer import seed_point_release
    from src.counterfactual.transport import forward_transport
    from src.drift.rk4 import RK45DriftEngine

    EARTH_M = 6_371_000.0

    def zero_velocity(lats, lons):
        return np.zeros_like(lats), np.zeros_like(lons)

    engine = RK45DriftEngine(velocity_func=zero_velocity, diffusivity_func=None)
    n = 10
    lats = np.full(n, seed_lat)
    lons = np.full(n, seed_lon)

    final_lats, final_lons, _ = engine.integrate(
        seed_lats=lats, seed_lons=lons,
        duration_hours=duration_hours, dt_minutes=dt_minutes,
        backward=False, seed=0,
    )

    dlat_m = np.abs(final_lats - lats) * (math.pi / 180.0) * EARTH_M
    dlon_m = np.abs(final_lons - lons) * (math.pi / 180.0) * EARTH_M * math.cos(
        math.radians(seed_lat)
    )
    displacement_m = np.sqrt(dlat_m ** 2 + dlon_m ** 2)

    if np.any(displacement_m > tolerance_m):
        raise AssertionError(
            f"Zero-velocity check FAILED: max displacement = "
            f"{np.max(displacement_m):.1f} m > tolerance {tolerance_m} m."
        )


def assert_constant_current_displacement(
    u_mps: float,
    v_mps: float,
    seed_lat: float,
    seed_lon: float,
    duration_hours: float = 1.0,
    dt_minutes: float = 10.0,
    tolerance_fraction: float = 0.01,
) -> None:
    """Physics sanity: constant current → analytical displacement matches RK45.

    Expected displacement:
        dy = v * duration_s  (metres, northward)
        dx = u * duration_s  (metres, eastward)
    """
    from src.drift.rk4 import RK45DriftEngine
    EARTH_M = 6_371_000.0

    def const_velocity(lats, lons):
        return (
            np.full_like(lats, u_mps),
            np.full_like(lats, v_mps),
        )

    engine = RK45DriftEngine(velocity_func=const_velocity, diffusivity_func=None)
    n = 1
    lats = np.array([seed_lat])
    lons = np.array([seed_lon])

    final_lats, final_lons, _ = engine.integrate(
        seed_lats=lats, seed_lons=lons,
        duration_hours=duration_hours, dt_minutes=dt_minutes,
        backward=False, seed=0,
    )

    duration_s = duration_hours * 3600.0
    expected_dy_m = v_mps * duration_s
    expected_dx_m = u_mps * duration_s

    actual_dy_m = (final_lats[0] - seed_lat) * (math.pi / 180.0) * EARTH_M
    actual_dx_m = (final_lons[0] - seed_lon) * (math.pi / 180.0) * EARTH_M * math.cos(
        math.radians(seed_lat)
    )

    for name, actual, expected in [("dy", actual_dy_m, expected_dy_m),
                                   ("dx", actual_dx_m, expected_dx_m)]:
        if abs(expected) > 1.0:
            err = abs(actual - expected) / abs(expected)
            if err > tolerance_fraction:
                raise AssertionError(
                    f"Constant-current check FAILED on {name}: "
                    f"expected {expected:.1f} m, got {actual:.1f} m "
                    f"(relative error {err:.3f} > {tolerance_fraction})."
                )


def assert_raster_coordinate_consistency(gt) -> None:
    """Coordinate round-trip: pixel → latlon → pixel yields same cell."""
    for row in [0, gt.height // 2, gt.height - 1]:
        for col in [0, gt.width // 2, gt.width - 1]:
            lat, lon = gt.pixel_to_latlon(col, row)
            col2, row2 = gt.latlon_to_pixel(lat, lon)
            if abs(col2 - col) > 1 or abs(row2 - row) > 1:
                raise AssertionError(
                    f"GeoTransform round-trip FAILED at ({row}, {col}): "
                    f"recovered ({row2}, {col2})."
                )


def assert_score_bounds(composite_score: float) -> None:
    """Composite score must be in [0, 1]."""
    if not (0.0 <= composite_score <= 1.0):
        raise AssertionError(
            f"Composite score out of bounds: {composite_score:.6f}. "
            "All metric weights must sum to 1 and individual metrics must be in [0, 1]."
        )


def assert_no_guilt_language(bundle) -> None:
    """Guard: bundle must not contain guilt or causation terminology."""
    forbidden = {
        "culprit", "guilty", "responsible_vessel", "guilt_probability",
        "causal_probability", "caused_by",
    }
    import dataclasses
    bundle_dict = dataclasses.asdict(bundle)
    bundle_str = str(bundle_dict).lower()
    for term in forbidden:
        if term in bundle_str:
            raise AssertionError(
                f"Forensic boundary violation: forbidden term '{term}' found in bundle."
            )
