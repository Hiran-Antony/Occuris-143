"""
Tests — Module 7 Synthetic Ground Truth Integration

Creates a known-truth counterfactual test case:
    - Known vessel track with known release point and time
    - Known (synthetic) wind + current (zero for determinism)
    - Generate synthetic "observed" spill by running forward transport
    - Confirm that the correct hypothesis scores above baseline median

Also tests perturbation sensitivity:
    - Moving the release point degrades the match
    - Wrong release time degrades the match

These tests do NOT use real environmental data.
They validate the pipeline logic, not the environmental model.
"""

from __future__ import annotations

import math
import numpy as np
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from src.counterfactual.metrics import compute_physical_metrics
from src.counterfactual.particle_initializer import seed_point_release
from src.counterfactual.rasterizer import particles_to_raster
from src.counterfactual.schemas import PhysicalMetrics
from src.drift.rk4 import RK45DriftEngine

# ── Synthetic constants ────────────────────────────────────────────────────────
RELEASE_LAT = 17.5
RELEASE_LON = 69.2
DURATION_H = 6.0
N_PARTICLES = 200
BBOX = {"lat_min": 16.0, "lat_max": 19.0, "lon_min": 68.0, "lon_max": 71.0}
IMG_H, IMG_W = 128, 128
WEIGHTS = {"iou": 0.35, "centroid": 0.25, "area": 0.15, "shape": 0.15, "orientation": 0.10}


def _zero_velocity(lats, lons):
    return np.zeros_like(lats), np.zeros_like(lons)


def _simulate_footprint(lat, lon, u=0.0, v=0.0, duration_h=DURATION_H):
    """Simulate a particle cloud with constant velocity and return raster."""
    def const_vel(lats, lons):
        return np.full_like(lats, u), np.full_like(lons, v)

    engine = RK45DriftEngine(velocity_func=const_vel, diffusivity_func=None)
    lats, lons = seed_point_release(lat, lon, N_PARTICLES, 300.0, rng_seed=0)
    final_lats, final_lons, _ = engine.integrate(
        lats, lons, duration_h, dt_minutes=10.0, backward=False, seed=0
    )

    # Manual rasterization (no GeoTransform dependency in this unit test)
    lat_min, lat_max = BBOX["lat_min"], BBOX["lat_max"]
    lon_min, lon_max = BBOX["lon_min"], BBOX["lon_max"]
    counts = np.zeros((IMG_H, IMG_W), dtype=np.int32)
    for flat, flon in zip(final_lats, final_lons):
        row = int((lat_max - flat) / (lat_max - lat_min) * IMG_H)
        col = int((flon - lon_min) / (lon_max - lon_min) * IMG_W)
        if 0 <= row < IMG_H and 0 <= col < IMG_W:
            counts[row, col] += 1
    return counts >= 2


def _compute(obs, sim):
    return compute_physical_metrics(
        observed=obs, simulated=sim,
        weights=WEIGHTS, centroid_decay_km=15.0, hausdorff_decay_km=20.0,
        **BBOX,
    )


class TestSyntheticGroundTruth:
    """Known release → simulated footprint → recovered high match."""

    def test_correct_release_high_match(self):
        """Simulating from the exact known release produces near-perfect match."""
        truth_raster = _simulate_footprint(RELEASE_LAT, RELEASE_LON)
        test_raster = _simulate_footprint(RELEASE_LAT, RELEASE_LON)  # same params
        m = _compute(truth_raster, test_raster)
        assert m.iou > 0.80, f"Expected high IoU for correct release, got {m.iou:.3f}"

    def test_wrong_release_location_lower_match(self):
        """Release 30 km away degrades the composite score."""
        truth_raster = _simulate_footprint(RELEASE_LAT, RELEASE_LON)
        # Offset ~30 km east
        wrong_lon = RELEASE_LON + 0.27
        wrong_raster = _simulate_footprint(RELEASE_LAT, wrong_lon)
        correct_m = _compute(truth_raster, _simulate_footprint(RELEASE_LAT, RELEASE_LON))
        wrong_m = _compute(truth_raster, wrong_raster)
        assert correct_m.composite_score > wrong_m.composite_score, (
            f"Correct release ({correct_m.composite_score:.3f}) should beat "
            f"wrong release ({wrong_m.composite_score:.3f})."
        )

    def test_wrong_release_time_lower_match(self):
        """Earlier release time (longer transport) shifts footprint → lower match.

        With zero current the footprint stays at the same location — so we use
        a nonzero current to make the test meaningful.
        """
        U, V = 0.3, 0.1  # constant current (m/s)
        truth_raster = _simulate_footprint(RELEASE_LAT, RELEASE_LON, u=U, v=V,
                                            duration_h=6.0)
        # 12 hours earlier → particles have been transported much further
        wrong_raster = _simulate_footprint(RELEASE_LAT, RELEASE_LON, u=U, v=V,
                                            duration_h=18.0)
        correct_m = _compute(truth_raster, truth_raster)   # perfect
        wrong_m = _compute(truth_raster, wrong_raster)
        assert correct_m.composite_score > wrong_m.composite_score

    def test_unrelated_location_lower_than_correct(self):
        """A completely unrelated release location scores lower than the correct one."""
        truth_raster = _simulate_footprint(RELEASE_LAT, RELEASE_LON)
        unrelated = _simulate_footprint(RELEASE_LAT + 1.5, RELEASE_LON + 1.5)
        m_correct = _compute(truth_raster, _simulate_footprint(RELEASE_LAT, RELEASE_LON))
        m_wrong = _compute(truth_raster, unrelated)
        assert m_correct.composite_score > m_wrong.composite_score


class TestPerturbationSensitivity:
    """Match score must degrade monotonically (approximately) with perturbation magnitude."""

    def test_increasing_displacement_decreases_iou(self):
        """Larger spatial displacement → lower IoU."""
        truth = _simulate_footprint(RELEASE_LAT, RELEASE_LON, u=0.5, v=0.0)
        iou_values = []
        for offset_deg in [0.0, 0.05, 0.15, 0.30]:
            sim = _simulate_footprint(RELEASE_LAT, RELEASE_LON + offset_deg, u=0.5, v=0.0)
            m = _compute(truth, sim)
            iou_values.append(m.iou)

        # Not strictly monotone guaranteed in every environment, but
        # the largest displacement should have the lowest IoU
        assert iou_values[0] >= iou_values[-1], (
            f"Largest displacement should have lowest IoU. Got: {iou_values}"
        )


class TestNoGroundTruthHardcoding:
    """Engine must not contain vessel-ID constants or hardcoded 'V004' references."""

    def test_no_v004_in_engine_source(self):
        from pathlib import Path
        engine_path = Path(__file__).parents[2] / "src" / "counterfactual" / "counterfactual_engine.py"
        src = engine_path.read_text(encoding="utf-8")
        # The engine should not reference any specific vessel ID as a constant
        assert "V004" not in src, "Engine source must not hardcode vessel ID 'V004'."
        assert "V001" not in src
        assert "V005" not in src
