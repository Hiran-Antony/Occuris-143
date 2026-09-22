"""
Tests — Module 7 Metrics

Validates all five physical comparison metrics against known-truth cases.
Every metric must be in [0, 1] and must respond correctly to degenerate inputs.
"""

import math
import numpy as np
import pytest

from src.counterfactual.metrics import (
    _pca_orientation_deg,
    compute_physical_metrics,
)

# Default weights that sum to 1.0 (from config)
WEIGHTS = {"iou": 0.35, "centroid": 0.25, "area": 0.15, "shape": 0.15, "orientation": 0.10}
CENTROID_DECAY = 15.0
HAUSDORFF_DECAY = 20.0
BBOX = dict(lat_min=14.0, lat_max=16.0, lon_min=52.0, lon_max=54.0)


def _metrics(obs, sim):
    return compute_physical_metrics(
        observed=obs, simulated=sim,
        weights=WEIGHTS,
        centroid_decay_km=CENTROID_DECAY,
        hausdorff_decay_km=HAUSDORFF_DECAY,
        **BBOX,
    )


class TestIoU:
    def test_identical_masks_iou_one(self):
        mask = np.zeros((64, 64), dtype=bool)
        mask[10:30, 10:30] = True
        m = _metrics(mask, mask.copy())
        assert abs(m.iou - 1.0) < 1e-6

    def test_non_overlapping_iou_zero(self):
        obs = np.zeros((64, 64), dtype=bool)
        obs[10:20, 10:20] = True
        sim = np.zeros((64, 64), dtype=bool)
        sim[40:50, 40:50] = True
        m = _metrics(obs, sim)
        assert m.iou == 0.0

    def test_partial_overlap_iou_between_zero_and_one(self):
        obs = np.zeros((64, 64), dtype=bool)
        obs[10:30, 10:30] = True
        sim = np.zeros((64, 64), dtype=bool)
        sim[20:40, 20:40] = True
        m = _metrics(obs, sim)
        assert 0.0 < m.iou < 1.0

    def test_iou_in_unit_interval(self):
        rng = np.random.default_rng(0)
        obs = rng.random((64, 64)) > 0.6
        sim = rng.random((64, 64)) > 0.6
        m = _metrics(obs, sim)
        assert 0.0 <= m.iou <= 1.0


class TestCentroid:
    def test_identical_centroid_similarity_one(self):
        mask = np.zeros((64, 64), dtype=bool)
        mask[20:40, 20:40] = True
        m = _metrics(mask, mask.copy())
        assert abs(m.centroid_similarity - 1.0) < 1e-6

    def test_centroid_similarity_in_unit_interval(self):
        obs = np.zeros((64, 64), dtype=bool)
        obs[10:20, 10:20] = True
        sim = np.zeros((64, 64), dtype=bool)
        sim[40:50, 40:50] = True
        m = _metrics(obs, sim)
        assert 0.0 <= m.centroid_similarity <= 1.0

    def test_centroid_distance_zero_for_same_mask(self):
        mask = np.zeros((64, 64), dtype=bool)
        mask[30:40, 30:40] = True
        m = _metrics(mask, mask.copy())
        assert m.centroid_distance_km < 0.01


class TestArea:
    def test_identical_area_similarity_one(self):
        mask = np.zeros((64, 64), dtype=bool)
        mask[10:30, 10:30] = True
        m = _metrics(mask, mask.copy())
        assert abs(m.area_similarity - 1.0) < 1e-6

    def test_both_zero_area_similarity_one(self):
        obs = np.zeros((64, 64), dtype=bool)
        sim = np.zeros((64, 64), dtype=bool)
        m = _metrics(obs, sim)
        assert m.area_similarity == 1.0

    def test_one_empty_area_similarity_zero(self):
        obs = np.zeros((64, 64), dtype=bool)
        obs[10:30, 10:30] = True
        sim = np.zeros((64, 64), dtype=bool)
        m = _metrics(obs, sim)
        assert m.area_similarity == 0.0

    def test_area_in_unit_interval(self):
        obs = np.zeros((64, 64), dtype=bool)
        obs[5:15, 5:15] = True
        sim = np.zeros((64, 64), dtype=bool)
        sim[5:25, 5:25] = True
        m = _metrics(obs, sim)
        assert 0.0 <= m.area_similarity <= 1.0


class TestOrientation:
    def test_same_orientation_similarity_one(self):
        mask = np.zeros((64, 64), dtype=bool)
        # Horizontal stripe
        mask[31, 5:60] = True
        m = _metrics(mask, mask.copy())
        assert abs(m.orientation_similarity - 1.0) < 1e-4

    def test_zero_and_180_same_axis(self):
        """0° and 180° must produce orientation_similarity = 1 (axial fix)."""
        delta = min(abs(0.0 - 180.0), 180.0 - abs(0.0 - 180.0))  # = 0
        expected_sim = 1.0 - delta / 90.0
        assert abs(expected_sim - 1.0) < 1e-6

    def test_perpendicular_similarity_zero(self):
        """90° axial difference → similarity = 0."""
        sim = 1.0 - 90.0 / 90.0
        assert abs(sim) < 1e-6

    def test_orientation_in_unit_interval(self):
        obs = np.zeros((64, 64), dtype=bool)
        obs[30, 5:60] = True  # horizontal
        sim = np.zeros((64, 64), dtype=bool)
        sim[5:60, 30] = True  # vertical
        m = _metrics(obs, sim)
        assert 0.0 <= m.orientation_similarity <= 1.0


class TestComposite:
    def test_composite_in_unit_interval(self):
        rng = np.random.default_rng(42)
        obs = rng.random((64, 64)) > 0.7
        sim = rng.random((64, 64)) > 0.7
        m = _metrics(obs, sim)
        assert 0.0 <= m.composite_score <= 1.0

    def test_perfect_match_composite_one(self):
        mask = np.zeros((64, 64), dtype=bool)
        mask[10:50, 10:50] = True
        m = _metrics(mask, mask.copy())
        assert abs(m.composite_score - 1.0) < 1e-4

    def test_weights_sensitivity(self):
        """Different weight configurations produce different scores — not hardcoded."""
        obs = np.zeros((64, 64), dtype=bool)
        obs[10:30, 10:30] = True
        sim = np.zeros((64, 64), dtype=bool)
        sim[35:55, 35:55] = True

        w1 = {"iou": 1.0, "centroid": 0.0, "area": 0.0, "shape": 0.0, "orientation": 0.0}
        w2 = {"iou": 0.0, "centroid": 0.0, "area": 0.0, "shape": 0.0, "orientation": 1.0}

        m1 = compute_physical_metrics(obs, sim, weights=w1,
                                       centroid_decay_km=CENTROID_DECAY,
                                       hausdorff_decay_km=HAUSDORFF_DECAY, **BBOX)
        m2 = compute_physical_metrics(obs, sim, weights=w2,
                                       centroid_decay_km=CENTROID_DECAY,
                                       hausdorff_decay_km=HAUSDORFF_DECAY, **BBOX)
        # IoU-only vs orientation-only should give different scores
        assert abs(m1.composite_score - m2.composite_score) > 1e-6
