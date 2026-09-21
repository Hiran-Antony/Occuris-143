"""
Module 6 — Property Tests
Tests invariants: determinism, score ranges, distribution sums, import guard.
"""

import pytest
import hashlib
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    AisGap,
    AisPing,
    BehaviourAssessment,
    BehaviourStatus,
    CaseContextV1,
    EvidenceBundleV1,
    ExplanationFactor,
    FactorSupportStatus,
    VesselJourney,
    VesselTrack,
)
from src.verification.pipeline import VerificationPipeline, load_verification_config


@pytest.fixture
def config():
    return load_verification_config()


@pytest.fixture
def pipeline(config):
    return VerificationPipeline(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def context(base_time):
    return CaseContextV1(
        case_id="case_01",
        release_window_start=base_time - timedelta(hours=24),
        release_window_end=base_time,
        spill_center={"lat": 14.8, "lon": 53.1},
    )


def _make_bundle(base_time):
    journey = VesselJourney(
        vessel_id="V_PROP",
        entry_time=base_time - timedelta(hours=10),
        exit_time=base_time + timedelta(hours=2),
    )
    gap = AisGap(
        vessel_id="V_PROP",
        gap_start=base_time - timedelta(hours=3),
        gap_end=base_time - timedelta(hours=2),
        duration_minutes=60.0,
        start_lat=16.0, start_lon=65.0,
        end_lat=16.1, end_lon=65.1,
    )
    assessment = BehaviourAssessment(
        vessel_id="V_PROP",
        status=BehaviourStatus.POTENTIAL_UNEXPLAINED_DELAY,
        explanations=[
            ExplanationFactor(factor="AIS_GAP", status=FactorSupportStatus.SUPPORTED,
                              detail="Gap detected"),
        ],
    )
    return EvidenceBundleV1(
        case_id="case_01", vessel_id="V_PROP",
        journey=journey, ais_gaps=[gap],
        behaviour_assessment=assessment,
    )


def _make_track(base_time):
    pings = []
    lat, lon = 16.0, 65.0
    for i in range(30):
        pings.append(AisPing(
            mmsi=477001001, vessel_id="V_PROP",
            timestamp=base_time - timedelta(hours=10) + timedelta(minutes=10 * i),
            lat=round(lat, 5), lon=round(lon, 5), sog=12.0, cog=90.0,
        ))
        lon += 0.02
    return VesselTrack(vessel_id="V_PROP", pings=pings)


class TestPropertyDeterminism:
    def test_two_runs_identical(self, pipeline, base_time, context):
        """Two runs with identical inputs must produce identical outputs."""
        bundle = _make_bundle(base_time)
        track = _make_track(base_time)

        r1 = pipeline.run(bundle, context, track=track)
        r2 = pipeline.run(bundle, context, track=track)

        # Core fields must be identical
        assert r1.ais_state == r2.ais_state
        assert r1.integrity_score == r2.integrity_score
        assert r1.integrity_interval == r2.integrity_interval
        assert r1.concealment_pattern_likelihood == r2.concealment_pattern_likelihood
        assert len(r1.anomaly_classifications) == len(r2.anomaly_classifications)


class TestPropertyScoreRanges:
    def test_integrity_in_unit_interval(self, pipeline, base_time, context):
        """Integrity score and interval must be in [0, 1]."""
        bundle = _make_bundle(base_time)
        track = _make_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        assert 0.0 <= result.integrity_score <= 1.0
        assert 0.0 <= result.integrity_interval[0] <= 1.0
        assert 0.0 <= result.integrity_interval[1] <= 1.0

    def test_concealment_in_unit_interval(self, pipeline, base_time, context):
        """Concealment likelihood must be in [0, 1]."""
        bundle = _make_bundle(base_time)
        track = _make_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        assert 0.0 <= result.concealment_pattern_likelihood <= 1.0

    def test_review_priority_non_negative(self, pipeline, base_time, context):
        """Review priority must be non-negative."""
        bundle = _make_bundle(base_time)
        track = _make_track(base_time)
        result = pipeline.run(bundle, context, track=track)
        assert result.review_priority >= 0.0


class TestPropertyDistributions:
    def test_explanation_distribution_sums(self, pipeline, base_time, context):
        """Global explanation distribution should sum to ~1.0 if non-empty."""
        bundle = _make_bundle(base_time)
        track = _make_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        if result.explanation_distribution:
            total = sum(result.explanation_distribution.values())
            assert abs(total - 1.0) < 0.05, f"Distribution sums to {total}"


class TestPropertyImportGuard:
    def test_no_drift_imports(self):
        """src/verification/ must NOT import from src/drift/."""
        import ast
        from pathlib import Path

        verification_dir = Path(__file__).resolve().parent.parent.parent / "src" / "verification"
        for py_file in verification_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "src.drift" in node.module:
                        pytest.fail(f"{py_file.name} imports from src.drift: {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "src.drift" in alias.name:
                            pytest.fail(f"{py_file.name} imports src.drift: {alias.name}")

    def test_no_attribution_imports(self):
        """src/verification/ must NOT import from src/attribution/."""
        import ast
        from pathlib import Path

        verification_dir = Path(__file__).resolve().parent.parent.parent / "src" / "verification"
        for py_file in verification_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "src.attribution" in node.module:
                        pytest.fail(f"{py_file.name} imports from src.attribution: {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "src.attribution" in alias.name:
                            pytest.fail(f"{py_file.name} imports src.attribution: {alias.name}")

    def test_ground_truth_isolation(self):
        """Production code in src/ must NOT read ground_truth.json."""
        import ast
        from pathlib import Path

        src_dir = Path(__file__).resolve().parent.parent.parent / "src"
        for py_file in src_dir.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            if "ground_truth" in source.lower() and "test" not in str(py_file).lower():
                # Allow comments but not actual file reads
                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if "ground_truth" in node.value.lower():
                            pytest.fail(
                                f"{py_file.name} references ground_truth in production code"
                            )
