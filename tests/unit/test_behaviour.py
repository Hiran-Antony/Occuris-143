"""Unit tests for src/ais/behaviour.py."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from src.ais.behaviour import BehaviourAuditor, WeatherProvider
from src.ais.schemas import (
    AISContinuity,
    AisGap,
    AisPing,
    BehaviourStatus,
    ExpectedTimeBasis,
    FactorSupportStatus,
    JourneyStatus,
    TransitAnalysis,
    VesselJourney,
    VesselTrack,
)


def make_track(v_id: str, pings_count: int = 5, has_gap: bool = False, nav_status: int = 0):
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    pings = [
        AisPing(
            mmsi=1234,
            vessel_id=v_id,
            timestamp=t0 + timedelta(minutes=10 * i),
            lat=16.0,
            lon=65.0 + 0.01 * i,
            sog=12.0,
            cog=90.0,
            nav_status=nav_status,
        )
        for i in range(pings_count)
    ]
    gaps = []
    if has_gap:
        gaps.append(
            AisGap(
                vessel_id=v_id,
                gap_start=t0 + timedelta(minutes=10),
                gap_end=t0 + timedelta(minutes=45),
                duration_minutes=35.0,
                start_lat=16.0,
                start_lon=65.01,
                end_lat=16.0,
                end_lon=65.02,
            )
        )
    return VesselTrack(
        vessel_id=v_id,
        pings=pings,
        total_distance_km=50.0,
        gaps=gaps,
        ais_continuity=AISContinuity.GAP_DETECTED if has_gap else AISContinuity.CONTINUOUS,
    )


def test_insufficient_data():
    auditor = BehaviourAuditor()
    track = VesselTrack(vessel_id="V_EMPTY", pings=[], total_distance_km=0.0)
    transit = TransitAnalysis(
        vessel_id="V_EMPTY",
        corridor_id="CORR",
        actual_duration_h=0.0,
        expected_basis=ExpectedTimeBasis.INSUFFICIENT_HISTORY,
    )
    journey = VesselJourney(
        journey_id="J1",
        vessel_id="V_EMPTY",
        distance_km=0.0,
        actual_duration_h=0.0,
        expected_basis=ExpectedTimeBasis.INSUFFICIENT_HISTORY,
        status=JourneyStatus.WINDOW_INTERIOR,
    )
    assessment = auditor.audit_vessel(track, journey, transit)
    assert assessment.status == BehaviourStatus.INSUFFICIENT_DATA


def test_normal_transit():
    auditor = BehaviourAuditor(delay_threshold_h=1.0)
    track = make_track("V_NORM", pings_count=5, has_gap=False)
    transit = TransitAnalysis(
        vessel_id="V_NORM",
        corridor_id="CORR",
        actual_duration_h=4.0,
        expected_duration_h=4.2,
        delay_h=-0.2,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
    )
    journey = VesselJourney(
        journey_id="J_NORM",
        vessel_id="V_NORM",
        distance_km=50.0,
        actual_duration_h=4.0,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
        status=JourneyStatus.COMPLETED,
    )
    assessment = auditor.audit_vessel(track, journey, transit)
    assert assessment.status == BehaviourStatus.NORMAL_TRANSIT


def test_explained_delay_nav_status():
    auditor = BehaviourAuditor(delay_threshold_h=1.0)
    # Vessel anchored (nav_status=1) with 3.0h delay
    track = make_track("V_ANCHOR", pings_count=5, has_gap=False, nav_status=1)
    transit = TransitAnalysis(
        vessel_id="V_ANCHOR",
        corridor_id="CORR",
        actual_duration_h=7.0,
        expected_duration_h=4.0,
        delay_h=3.0,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
    )
    journey = VesselJourney(
        journey_id="J_ANCHOR",
        vessel_id="V_ANCHOR",
        distance_km=50.0,
        actual_duration_h=7.0,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
        status=JourneyStatus.COMPLETED,
    )
    assessment = auditor.audit_vessel(track, journey, transit)
    assert assessment.status == BehaviourStatus.EXPLAINED_DELAY
    nav_factor = next((f for f in assessment.explanations if f.factor == "NAV_STATUS"), None)
    assert nav_factor is not None
    assert nav_factor.status == FactorSupportStatus.SUPPORTED


def test_potential_unexplained_delay_blackout():
    auditor = BehaviourAuditor(delay_threshold_h=1.0, wind_threshold_ms=15.0)
    # Vessel with 35-min blackout and delay
    track = make_track("V_DARK", pings_count=5, has_gap=True)
    transit = TransitAnalysis(
        vessel_id="V_DARK",
        corridor_id="CORR",
        actual_duration_h=6.5,
        expected_duration_h=4.0,
        delay_h=2.5,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
    )
    journey = VesselJourney(
        journey_id="J_DARK",
        vessel_id="V_DARK",
        distance_km=50.0,
        actual_duration_h=6.5,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
        status=JourneyStatus.COMPLETED,
    )
    assessment = auditor.audit_vessel(track, journey, transit)
    assert assessment.status == BehaviourStatus.POTENTIAL_UNEXPLAINED_DELAY
    gap_factor = next((f for f in assessment.explanations if f.factor == "AIS_GAP"), None)
    assert gap_factor is not None
    assert gap_factor.status == FactorSupportStatus.SUPPORTED
