"""Unit tests for src/ais/delay_analysis.py."""

from datetime import datetime, timezone
import pytest

from src.ais.delay_analysis import DelayAnalyzer
from src.ais.schemas import (
    ExpectedTimeBasis,
    JourneyStatus,
    VesselJourney,
)


def make_journey(v_id: str, dist_km: float, dur_h: float, entry="GATE_A", exit="GATE_B"):
    return VesselJourney(
        journey_id=f"J_{v_id}",
        vessel_id=v_id,
        entry_gateway=entry,
        entry_time=datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc),
        exit_gateway=exit,
        exit_time=datetime(2024, 3, 15, int(dur_h), 0, tzinfo=timezone.utc),
        distance_km=dist_km,
        actual_duration_h=dur_h,
        average_speed_kn=round((dist_km * 0.539957) / dur_h, 1),
        max_observed_speed_kn=14.0,
        dominant_course_deg=90.0,
        expected_basis=ExpectedTimeBasis.INSUFFICIENT_HISTORY,
        status=JourneyStatus.COMPLETED,
    )


def test_corridor_baseline_fallback():
    analyzer = DelayAnalyzer(min_history_journeys=5, default_baseline_speed_kn=12.0)
    # Vessel with no history: distance 200 km, actual duration 10h
    # 200 km = 107.99 NM. At 12 kn, expected time = 107.99 / 12 = ~9.0h
    # Delay = 10.0 - 9.0 = ~1.0h
    j = make_journey("V01", dist_km=200.0, dur_h=10.0)
    analysis = analyzer.analyze_journey(j, history=[])

    assert analysis.expected_basis == ExpectedTimeBasis.CORRIDOR_BASELINE
    assert analysis.expected_duration_h is not None
    assert 8.8 < analysis.expected_duration_h < 9.2
    assert analysis.delay_h is not None
    assert 0.8 < analysis.delay_h < 1.2
    assert analysis.z_score is None  # No distribution for single vessel baseline


def test_historical_zscore_analysis():
    # 6 historical journeys with mean duration 5.0h and non-zero std
    durations = [4.5, 4.8, 5.0, 5.2, 5.5, 5.0]
    history = [make_journey("V_HIST", dist_km=100.0, dur_h=d) for d in durations]

    analyzer = DelayAnalyzer(min_history_journeys=5)
    # Current journey took 8.0h (significantly delayed)
    curr_j = make_journey("V_HIST", dist_km=100.0, dur_h=8.0)
    analysis = analyzer.analyze_journey(curr_j, history=history)

    assert analysis.expected_basis == ExpectedTimeBasis.HISTORICAL
    assert analysis.expected_duration_h is not None
    assert abs(analysis.expected_duration_h - 5.0) < 0.2
    assert analysis.delay_h is not None
    assert analysis.delay_h > 2.5
    assert analysis.z_score is not None
    assert analysis.z_score > 3.0  # Multi-sigma outlier
