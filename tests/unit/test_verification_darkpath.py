"""
Module 6 — Unit Tests: Dark Path Validator (Stage 5)
Tests feasibility checks, origin zone intersection, and disclaimer preservation.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    CandidateDarkPath,
    CaseContextV1,
    DarkPathHypothesis,
    EvidenceBundleV1,
    VerificationStageStatus,
)
from src.verification.dark_path_validator import DarkPathValidator


@pytest.fixture
def config():
    return {
        "reachability": {"current_boost_kn": 2.0, "current_assist": True},
        "_region": {"vessel_class_max_speeds_kn": {"default": 18.0}},
    }


@pytest.fixture
def validator(config):
    return DarkPathValidator(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 3, 0, 0, tzinfo=timezone.utc)


def _make_hypothesis(vessel_id, base_time, paths):
    return DarkPathHypothesis(
        hypothesis_id=f"HYP_{vessel_id}",
        vessel_id=vessel_id,
        gap_start=base_time,
        gap_end=base_time + timedelta(hours=1),
        start_lat=16.0, start_lon=65.0,
        end_lat=16.1, end_lon=65.1,
        paths=paths,
    )


def _make_context():
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return CaseContextV1(
        case_id="case_01",
        release_window_start=base,
        release_window_end=base + timedelta(hours=24),
        spill_center={"lat": 14.8, "lon": 53.1},
    )


class TestDarkPathValidator:
    def test_no_hypotheses(self, validator):
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V001")
        result = validator.validate(bundle, _make_context())
        assert result.hypotheses_evaluated == 0
        assert result.status == VerificationStageStatus.SKIPPED

    def test_feasible_path_no_intersection(self, validator, base_time):
        path = CandidateDarkPath(
            path_type="geodesic",
            coordinates=[(65.0, 16.0), (65.1, 16.1)],
            length_km=15.0,
            implied_speed_knots=10.0,
            feasible=True,
            probability=0.4,
            intersects_origin=False,
        )
        hyp = _make_hypothesis("V001", base_time, [path])
        bundle = EvidenceBundleV1(
            case_id="case_01", vessel_id="V001",
            dark_path_hypotheses=[hyp],
        )
        result = validator.validate(bundle, _make_context())
        assert result.hypotheses_evaluated == 1
        assert result.dark_path_support is False
        assert result.entries[0].valid is True
        assert result.entries[0].intersects_origin is False

    def test_feasible_path_with_intersection(self, validator, base_time):
        path = CandidateDarkPath(
            path_type="geodesic",
            coordinates=[(65.0, 16.0), (53.1, 14.8)],
            length_km=100.0,
            implied_speed_knots=15.0,
            feasible=True,
            probability=0.6,
            intersects_origin=True,
        )
        hyp = _make_hypothesis("V003", base_time, [path])
        bundle = EvidenceBundleV1(
            case_id="case_01", vessel_id="V003",
            dark_path_hypotheses=[hyp],
        )
        result = validator.validate(bundle, _make_context())
        assert result.dark_path_support is True
        assert result.status == VerificationStageStatus.FLAGGED

    def test_infeasible_path(self, validator, base_time):
        path = CandidateDarkPath(
            path_type="geodesic",
            coordinates=[(65.0, 16.0), (53.1, 14.8)],
            length_km=1000.0,
            implied_speed_knots=50.0,  # Way over limit
            feasible=False,
            probability=0.1,
            intersects_origin=True,
        )
        hyp = _make_hypothesis("V_INF", base_time, [path])
        bundle = EvidenceBundleV1(
            case_id="case_01", vessel_id="V_INF",
            dark_path_hypotheses=[hyp],
        )
        result = validator.validate(bundle, _make_context())
        assert result.entries[0].valid is False
        assert result.dark_path_support is False

    def test_disclaimer_preserved(self, validator, base_time):
        path = CandidateDarkPath(
            path_type="geodesic",
            coordinates=[(65.0, 16.0), (65.1, 16.1)],
            length_km=15.0,
            implied_speed_knots=10.0,
            feasible=True,
            probability=0.5,
            intersects_origin=False,
        )
        hyp = _make_hypothesis("V001", base_time, [path])
        bundle = EvidenceBundleV1(
            case_id="case_01", vessel_id="V001",
            dark_path_hypotheses=[hyp],
        )
        result = validator.validate(bundle, _make_context())
        assert "HYPOTHESIS" in result.entries[0].disclaimer
        assert "not observed" in result.entries[0].disclaimer
