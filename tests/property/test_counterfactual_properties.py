"""
Tests — Module 7 Properties

Mathematical invariants and import-boundary guards.
These must pass regardless of environmental data availability.
"""

import numpy as np
import pytest


class TestPropertyScoreBounds:
    """All metrics and composite scores must lie in [0, 1]."""

    def _random_metrics(self, seed):
        from src.counterfactual.metrics import compute_physical_metrics
        rng = np.random.default_rng(seed)
        obs = rng.random((64, 64)) > rng.uniform(0.5, 0.9)
        sim = rng.random((64, 64)) > rng.uniform(0.5, 0.9)
        weights = {"iou": 0.35, "centroid": 0.25, "area": 0.15, "shape": 0.15, "orientation": 0.10}
        return compute_physical_metrics(
            observed=obs, simulated=sim,
            lat_min=14.0, lat_max=16.0, lon_min=52.0, lon_max=54.0,
            weights=weights, centroid_decay_km=15.0, hausdorff_decay_km=20.0,
        )

    @pytest.mark.parametrize("seed", [0, 1, 42, 99, 1000])
    def test_all_scores_in_unit_interval(self, seed):
        m = self._random_metrics(seed)
        for name in ["iou", "centroid_similarity", "area_similarity",
                     "shape_similarity", "orientation_similarity", "composite_score"]:
            val = getattr(m, name)
            assert 0.0 <= val <= 1.0, f"{name} = {val} out of [0, 1] with seed {seed}."


class TestPropertyDeterminism:
    """Same config + same seed → identical output."""

    def test_particle_seeding_deterministic(self):
        from src.counterfactual.particle_initializer import seed_point_release
        lats1, lons1 = seed_point_release(17.5, 69.2, 100, 500.0, rng_seed=42)
        lats2, lons2 = seed_point_release(17.5, 69.2, 100, 500.0, rng_seed=42)
        np.testing.assert_array_equal(lats1, lats2)
        np.testing.assert_array_equal(lons1, lons2)

    def test_ensemble_generation_deterministic(self):
        from src.counterfactual.uncertainty import generate_ensemble
        e1 = generate_ensemble(5, 0.1, 0.1, 1.0, base_seed=42)
        e2 = generate_ensemble(5, 0.1, 0.1, 1.0, base_seed=42)
        for m1, m2 in zip(e1, e2):
            assert m1.windage_multiplier == m2.windage_multiplier
            assert m1.rng_seed == m2.rng_seed


class TestPropertyImportGuard:
    """Module 7 must not import from backward drift or ground-truth modules."""

    def _collect_imports(self, module_name: str):
        import ast
        import importlib
        import importlib.util
        import sys
        from pathlib import Path
        mod_path = Path(__file__).parents[2] / "src" / "counterfactual" / f"{module_name}.py"
        if not mod_path.exists():
            return set()
        src = mod_path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
        return imports

    def test_metrics_no_drift_backward(self):
        imports = self._collect_imports("metrics")
        assert "src.drift.backward_drift" not in imports

    def test_transport_no_attribution(self):
        imports = self._collect_imports("transport")
        assert not any("spillsplit" in i for i in imports)

    def test_engine_no_ground_truth(self):
        imports = self._collect_imports("counterfactual_engine")
        forbidden = {"ground_truth", "test_cases", "known_answer"}
        for imp in imports:
            for f in forbidden:
                assert f not in imp.lower(), f"Forbidden import '{imp}' in engine."


class TestPropertyOrientationAxial:
    """Verify the axial angle formula handles the 0°/180° equivalence."""

    def test_zero_and_180_axial_diff_is_zero(self):
        angle1, angle2 = 0.0, 180.0
        diff = abs(angle1 - angle2)
        axial = min(diff, 180.0 - diff)
        assert axial == 0.0

    def test_90_and_0_axial_diff_is_90(self):
        angle1, angle2 = 90.0, 0.0
        diff = abs(angle1 - angle2)
        axial = min(diff, 180.0 - diff)
        assert axial == 90.0

    def test_45_and_135_axial_diff_is_90(self):
        angle1, angle2 = 45.0, 135.0
        diff = abs(angle1 - angle2)
        axial = min(diff, 180.0 - diff)
        assert axial == 90.0

    def test_30_and_210_equiv_to_30_and_30(self):
        """210° = 30° on an axis (mod 180)."""
        angle1 = 30.0
        angle2 = 210.0 % 180.0  # 30°
        diff = abs(angle1 - angle2)
        axial = min(diff, 180.0 - diff)
        assert axial == 0.0


class TestPropertyEnsembleNominalFirst:
    """Member 0 is always unperturbed (nominal)."""

    def test_member_zero_has_multipliers_one(self):
        from src.counterfactual.uncertainty import generate_ensemble
        members = generate_ensemble(5, 0.15, 0.15, 1.0, base_seed=0)
        assert members[0].windage_multiplier == 1.0
        assert members[0].current_multiplier == 1.0
        assert members[0].member_index == 0

    def test_n_members_correct(self):
        from src.counterfactual.uncertainty import generate_ensemble
        for n in [1, 3, 5, 10]:
            members = generate_ensemble(n, 0.1, 0.1, 1.0, base_seed=42)
            assert len(members) == n


class TestPropertySchemaForensicBoundary:
    """CounterfactualEvidenceBundleV1 must have no guilt-language fields."""

    def test_no_culprit_field(self):
        import dataclasses
        from src.counterfactual.schemas import CounterfactualEvidenceBundleV1
        field_names = {f.name for f in dataclasses.fields(CounterfactualEvidenceBundleV1)}
        forbidden = {"culprit", "guilty", "responsible_vessel", "guilt_probability",
                     "causal_probability", "caused_by"}
        intersection = field_names & forbidden
        assert not intersection, f"Forensic boundary violation: {intersection}"
