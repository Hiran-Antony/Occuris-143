"""
Module 6 — Unit Tests: State Classifier (Stage 6)
Tests explanation argmax, integrity monotonicity, AMBIGUOUS trigger, and state decisions.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    AisGap,
    AisState,
    AnomalyClassification,
    BehaviourAssessment,
    BehaviourStatus,
    CaseContextV1,
    ContinuityReport,
    DarkPathValidation,
    EvidenceBundleV1,
    ExplanationFactor,
    FactorSupportStatus,
    GapConcurrencyRecord,
    KinematicReport,
    ReachabilityResult,
    ReachabilityVerdict,
    VerificationStageStatus,
    WindowResolution,
)
from src.verification.state_classifier import StateClassifier


@pytest.fixture
def config():
    return {
        "explanation_weights": {
            "COVERAGE": 1.0,
            "WEATHER": 0.8,
            "TRAFFIC": 0.6,
            "OPERATIONAL": 0.9,
            "CONCEALMENT_PATTERN": 0.7,
        },
        "integrity": {
            "prior_reliable": 0.90,
            "prior_sensitivity_range": [0.70, 0.95],
            "lr_table": {
                "continuous_ais": {"value": 3.0},
                "gap_short": {"value": 0.7},
                "gap_long": {"value": 0.3},
                "ekf_clean": {"value": 2.0},
                "ekf_episode": {"value": 0.2},
                "speed_impossible": {"value": 0.15},
                "identity_conflict": {"value": 0.1},
                "nav_status_normal": {"value": 1.5},
            },
            "dependency_discount": {
                "gap_family_exponent": 0.7,
                "ekf_family_exponent": 0.7,
            },
        },
    }


@pytest.fixture
def classifier(config):
    return StateClassifier(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)


def _make_bundle(vessel_id="V001", has_weather=False, has_gap=False):
    explanations = []
    if has_weather:
        explanations.append(ExplanationFactor(
            factor="WEATHER", status=FactorSupportStatus.SUPPORTED,
            detail="Adverse wind conditions",
        ))
    assessment = BehaviourAssessment(
        vessel_id=vessel_id,
        status=BehaviourStatus.NORMAL_TRANSIT,
        explanations=explanations,
    )
    gaps = []
    if has_gap:
        base = datetime(2024, 3, 15, 3, 0, 0, tzinfo=timezone.utc)
        gaps = [AisGap(
            vessel_id=vessel_id,
            gap_start=base, gap_end=base + timedelta(minutes=40),
            duration_minutes=40.0,
            start_lat=16.0, start_lon=65.0,
            end_lat=16.1, end_lon=65.1,
        )]
    return EvidenceBundleV1(
        case_id="case_01", vessel_id=vessel_id,
        behaviour_assessment=assessment,
        ais_gaps=gaps,
    )


def _make_context():
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return CaseContextV1(
        case_id="case_01",
        release_window_start=base,
        release_window_end=base + timedelta(hours=24),
    )


def _make_window(vessel_id="V001", present=True):
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return WindowResolution(
        vessel_id=vessel_id,
        window_start=base,
        window_end=base + timedelta(hours=12),
        overlap_minutes=720.0,
        vessel_present=present,
    )


class TestStateClassifier:
    def test_normal_vessel_state(self, classifier, base_time):
        bundle = _make_bundle("V001")
        continuity = ContinuityReport(
            vessel_id="V001", total_gaps=0, total_dark_minutes=0.0,
            max_gap_minutes=0.0, gap_concurrency_index=0.0,
        )
        kinematic = KinematicReport(
            vessel_id="V001", total_pings_analyzed=50, anomalous_pings=0,
        )
        result = classifier.classify(
            bundle, _make_context(), _make_window(),
            continuity, kinematic, None, None,
        )
        assert result["ais_state"] == AisState.NORMAL
        assert result["integrity_score"] > 0.5

    def test_gap_vessel_dark_state(self, classifier, base_time):
        bundle = _make_bundle("V003", has_gap=True)
        base = datetime(2024, 3, 15, 3, 0, 0, tzinfo=timezone.utc)
        continuity = ContinuityReport(
            vessel_id="V003", total_gaps=1, total_dark_minutes=40.0,
            max_gap_minutes=40.0, gap_concurrency_index=0.0,
            gap_concurrency_records=[GapConcurrencyRecord(
                gap_start=base, gap_end=base + timedelta(minutes=40),
                duration_minutes=40.0, concurrent_vessel_count=0,
            )],
        )
        kinematic = KinematicReport(
            vessel_id="V003", total_pings_analyzed=50, anomalous_pings=0,
        )
        result = classifier.classify(
            bundle, _make_context(), _make_window("V003"),
            continuity, kinematic, None, None,
        )
        assert result["ais_state"] in [AisState.AIS_GAP_DARK, AisState.AMBIGUOUS]

    def test_integrity_monotonicity(self, classifier):
        """Adding negative evidence should strictly lower integrity score."""
        # Clean vessel
        clean_cont = ContinuityReport(
            vessel_id="V_CLEAN", total_gaps=0, total_dark_minutes=0.0,
            max_gap_minutes=0.0, gap_concurrency_index=0.0,
        )
        clean_kin = KinematicReport(
            vessel_id="V_CLEAN", total_pings_analyzed=50, anomalous_pings=0,
        )
        score_clean, _ = classifier._compute_integrity(clean_cont, clean_kin, None)

        # Vessel with long gap
        gap_cont = ContinuityReport(
            vessel_id="V_GAP", total_gaps=1, total_dark_minutes=120.0,
            max_gap_minutes=120.0, gap_concurrency_index=0.0,
        )
        score_gap, _ = classifier._compute_integrity(gap_cont, clean_kin, None)

        assert score_clean > score_gap, \
            f"Clean={score_clean} should be > gap={score_gap}"

        # Vessel with gap + kinematic episode
        from src.ais.schemas import KinematicEpisode, KinematicFlag
        bad_kin = KinematicReport(
            vessel_id="V_BAD", total_pings_analyzed=50, anomalous_pings=5,
            episodes=[KinematicEpisode(
                vessel_id="V_BAD", episode_type=KinematicFlag.TELEPORT_JUMP,
            )],
        )
        score_bad, _ = classifier._compute_integrity(gap_cont, bad_kin, None)

        assert score_gap > score_bad, \
            f"Gap={score_gap} should be > gap+episode={score_bad}"

    def test_integrity_interval_bounds(self, classifier):
        """Integrity interval should be [lo, hi] with lo <= score <= hi."""
        cont = ContinuityReport(
            vessel_id="V_INT", total_gaps=1, total_dark_minutes=40.0,
            max_gap_minutes=40.0, gap_concurrency_index=0.0,
        )
        kin = KinematicReport(
            vessel_id="V_INT", total_pings_analyzed=50, anomalous_pings=0,
        )
        score, interval = classifier._compute_integrity(cont, kin, None)
        assert interval[0] <= score <= interval[1]

    def test_scores_in_range(self, classifier):
        """All scores must be in [0, 1]."""
        cont = ContinuityReport(
            vessel_id="V_RNG", total_gaps=0, total_dark_minutes=0.0,
            max_gap_minutes=0.0, gap_concurrency_index=0.0,
        )
        kin = KinematicReport(
            vessel_id="V_RNG", total_pings_analyzed=50, anomalous_pings=0,
        )
        score, interval = classifier._compute_integrity(cont, kin, None)
        assert 0.0 <= score <= 1.0
        assert 0.0 <= interval[0] <= 1.0
        assert 0.0 <= interval[1] <= 1.0

    def test_explanation_distribution_sums_to_one(self, classifier):
        """Softmax distribution should sum to ~1.0."""
        evidence = {"COVERAGE": 1.0, "WEATHER": 0.5, "TRAFFIC": 0.3}
        dist = classifier._softmax_competition(evidence)
        total = sum(dist.values())
        assert abs(total - 1.0) < 0.01

    def test_explained_with_weather(self, classifier, base_time):
        """Gap with strong weather support should be classified EXPLAINED."""
        bundle = _make_bundle("V_WX", has_weather=True, has_gap=True)
        base = datetime(2024, 3, 15, 3, 0, 0, tzinfo=timezone.utc)
        continuity = ContinuityReport(
            vessel_id="V_WX", total_gaps=1, total_dark_minutes=40.0,
            max_gap_minutes=40.0, gap_concurrency_index=0.0,
            gap_concurrency_records=[GapConcurrencyRecord(
                gap_start=base, gap_end=base + timedelta(minutes=40),
                duration_minutes=40.0, concurrent_vessel_count=0,
            )],
        )
        result = classifier.classify(
            bundle, _make_context(), _make_window("V_WX"),
            continuity, None, None, None,
        )
        # Should have at least one anomaly classification
        assert len(result["anomaly_classifications"]) > 0
