"""
Module 6 — Unit Tests: Window Resolver (Stage 1)
Tests investigation window intersection math.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    CaseContextV1,
    EvidenceBundleV1,
    VesselJourney,
    VerificationStageStatus,
)
from src.verification.window_resolver import WindowResolver


@pytest.fixture
def config():
    return {"window_pad_min": 60}


@pytest.fixture
def resolver(config):
    return WindowResolver(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 6, 0, 0, tzinfo=timezone.utc)


def _make_bundle(vessel_id="V001", entry_time=None, exit_time=None):
    journey = None
    if entry_time or exit_time:
        journey = VesselJourney(
            vessel_id=vessel_id,
            entry_time=entry_time,
            exit_time=exit_time,
        )
    return EvidenceBundleV1(case_id="case_01", vessel_id=vessel_id, journey=journey)


def _make_context(case_id="case_01", start=None, end=None):
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return CaseContextV1(
        case_id=case_id,
        release_window_start=start or base,
        release_window_end=end or (base + timedelta(hours=24)),
    )


class TestWindowResolver:
    def test_vessel_fully_within_window(self, resolver, base_time):
        bundle = _make_bundle(
            entry_time=base_time - timedelta(hours=6),
            exit_time=base_time + timedelta(hours=6),
        )
        context = _make_context(
            start=base_time - timedelta(hours=12),
            end=base_time + timedelta(hours=12),
        )
        result = resolver.resolve(bundle, context)
        assert result.vessel_present is True
        assert result.overlap_minutes > 0
        assert result.status == VerificationStageStatus.PASSED

    def test_vessel_outside_window(self, resolver, base_time):
        bundle = _make_bundle(
            entry_time=base_time + timedelta(hours=48),
            exit_time=base_time + timedelta(hours=72),
        )
        context = _make_context(
            start=base_time,
            end=base_time + timedelta(hours=24),
        )
        result = resolver.resolve(bundle, context)
        assert result.vessel_present is False
        assert result.overlap_minutes == 0.0
        assert result.status == VerificationStageStatus.SKIPPED

    def test_partial_overlap(self, resolver, base_time):
        bundle = _make_bundle(
            entry_time=base_time + timedelta(hours=20),
            exit_time=base_time + timedelta(hours=30),
        )
        context = _make_context(
            start=base_time,
            end=base_time + timedelta(hours=24),
        )
        # With 60 min padding, release window extends to +25h
        result = resolver.resolve(bundle, context)
        assert result.vessel_present is True
        assert result.overlap_minutes > 0

    def test_no_journey_data(self, resolver, base_time):
        bundle = _make_bundle()
        context = _make_context(start=base_time, end=base_time + timedelta(hours=24))
        result = resolver.resolve(bundle, context)
        assert result.vessel_present is False

    def test_padding_extends_window(self, resolver, base_time):
        """Window pad should extend release window by 60 min each side."""
        bundle = _make_bundle(
            entry_time=base_time - timedelta(minutes=30),
            exit_time=base_time + timedelta(hours=1),
        )
        # Release window starts exactly at base_time
        context = _make_context(
            start=base_time,
            end=base_time + timedelta(hours=1),
        )
        result = resolver.resolve(bundle, context)
        assert result.vessel_present is True
        # Overlap should include the padded pre-window portion
        assert result.overlap_minutes >= 30.0

    def test_origin_zone_ref(self, resolver, base_time):
        bundle = _make_bundle(
            entry_time=base_time,
            exit_time=base_time + timedelta(hours=6),
        )
        context = CaseContextV1(
            case_id="case_02",
            origin_zones=[{"id": "ZONE_ALPHA", "type": "Polygon"}],
            release_window_start=base_time,
            release_window_end=base_time + timedelta(hours=12),
        )
        result = resolver.resolve(bundle, context)
        assert result.origin_zone_ref == "ZONE_ALPHA"
