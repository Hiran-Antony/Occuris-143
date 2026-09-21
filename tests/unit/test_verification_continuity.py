"""
Module 6 — Unit Tests: Continuity Analyzer (Stage 2)
Tests gap statistics, concurrency index, and COVERAGE support flag.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    AisGap,
    CaseContextV1,
    ContinuityReport,
    EvidenceBundleV1,
    VerificationStageStatus,
)
from src.verification.continuity_analyzer import ContinuityAnalyzer


@pytest.fixture
def config():
    return {
        "concurrency": {
            "window_min": 15,
            "coverage_min_vessels": 3,
            "radius_nm": 20,
        }
    }


@pytest.fixture
def analyzer(config):
    return ContinuityAnalyzer(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 3, 0, 0, tzinfo=timezone.utc)


def _make_gap(vessel_id, start, duration_min, lat=16.0, lon=65.0):
    return AisGap(
        vessel_id=vessel_id,
        gap_start=start,
        gap_end=start + timedelta(minutes=duration_min),
        duration_minutes=duration_min,
        start_lat=lat, start_lon=lon,
        end_lat=lat + 0.01, end_lon=lon + 0.01,
    )


def _make_bundle(vessel_id, gaps):
    return EvidenceBundleV1(case_id="case_01", vessel_id=vessel_id, ais_gaps=gaps)


def _make_context():
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return CaseContextV1(
        case_id="case_01",
        release_window_start=base,
        release_window_end=base + timedelta(hours=24),
    )


class TestContinuityAnalyzer:
    def test_no_gaps(self, analyzer, base_time):
        bundle = _make_bundle("V001", [])
        result = analyzer.analyze(bundle, _make_context(), [bundle])
        assert result.total_gaps == 0
        assert result.total_dark_minutes == 0.0
        assert result.status == VerificationStageStatus.PASSED

    def test_single_gap_statistics(self, analyzer, base_time):
        gap = _make_gap("V003", base_time, 38.0)
        bundle = _make_bundle("V003", [gap])
        result = analyzer.analyze(bundle, _make_context(), [bundle])
        assert result.total_gaps == 1
        assert result.total_dark_minutes == 38.0
        assert result.max_gap_minutes == 38.0

    def test_concurrency_index_solo(self, analyzer, base_time):
        """Solo gap (no other vessels gapped) should have concurrency_index = 0."""
        gap = _make_gap("V003", base_time, 38.0)
        bundle = _make_bundle("V003", [gap])
        other = _make_bundle("V001", [])
        result = analyzer.analyze(bundle, _make_context(), [bundle, other])
        assert result.gap_concurrency_index == 0.0
        assert result.coverage_support is False

    def test_concurrency_index_concurrent(self, analyzer, base_time):
        """Multiple concurrent gaps should increase concurrency index."""
        gap_main = _make_gap("V003", base_time, 38.0)
        bundle = _make_bundle("V003", [gap_main])

        # Create 3 other vessels with overlapping gaps nearby
        others = []
        for i in range(3):
            g = _make_gap(f"V00{i+6}", base_time + timedelta(minutes=5), 20.0,
                          lat=16.01, lon=65.01)
            others.append(_make_bundle(f"V00{i+6}", [g]))

        all_bundles = [bundle] + others
        result = analyzer.analyze(bundle, _make_context(), all_bundles)
        assert result.gap_concurrency_index > 0.0
        assert result.coverage_support is True
        assert result.gap_concurrency_records[0].coverage_flag is True

    def test_non_overlapping_gaps(self, analyzer, base_time):
        """Gaps far apart in time should not count as concurrent."""
        gap_main = _make_gap("V003", base_time, 20.0)
        bundle = _make_bundle("V003", [gap_main])
        g_other = _make_gap("V006", base_time + timedelta(hours=5), 20.0)
        other = _make_bundle("V006", [g_other])
        result = analyzer.analyze(bundle, _make_context(), [bundle, other])
        assert result.gap_concurrency_records[0].concurrent_vessel_count == 0

    def test_flagged_when_solo_gap(self, analyzer, base_time):
        """Solo gap should produce FLAGGED status."""
        gap = _make_gap("V003", base_time, 38.0)
        bundle = _make_bundle("V003", [gap])
        result = analyzer.analyze(bundle, _make_context(), [bundle])
        assert result.status == VerificationStageStatus.FLAGGED
