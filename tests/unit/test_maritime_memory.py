"""Unit tests for src/ais/maritime_memory.py."""

from datetime import datetime, timedelta, timezone
import pytest

from src.ais.maritime_memory import MaritimeMemory
from src.ais.schemas import (
    EventType,
    GatewayCrossingEvent,
    JourneyStatus,
    AisPing,
    VesselTrack,
)


def test_completed_journey():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=5)

    pings = [
        AisPing(mmsi=1, vessel_id="V01", timestamp=t0, lat=18.0, lon=65.0, sog=12.0, cog=180.0, nav_status=0),
        AisPing(mmsi=1, vessel_id="V01", timestamp=t1, lat=15.0, lon=65.0, sog=12.0, cog=180.0, nav_status=0),
    ]
    track = VesselTrack(vessel_id="V01", pings=pings, total_distance_km=333.0)

    crossings = [
        GatewayCrossingEvent(
            event_id="E1",
            vessel_id="V01",
            gateway_id="GATE_B",
            event_type=EventType.ENTRY,
            timestamp=t0 + timedelta(minutes=30),
            latitude=17.8,
            longitude=65.0,
        ),
        GatewayCrossingEvent(
            event_id="E2",
            vessel_id="V01",
            gateway_id="GATE_C",
            event_type=EventType.EXIT,
            timestamp=t1 - timedelta(minutes=30),
            latitude=15.2,
            longitude=65.0,
        ),
    ]

    memory = MaritimeMemory()
    journeys = memory.build_journeys({"V01": track}, crossings)

    assert "V01" in journeys
    j = journeys["V01"]
    assert j.status == JourneyStatus.COMPLETED
    assert j.entry_gateway == "GATE_B"
    assert j.exit_gateway == "GATE_C"
    assert j.actual_duration_h == 5.0
    assert j.max_observed_speed_kn == 12.0
    assert j.dominant_course_deg == 180.0


def test_in_region_journey():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=3)

    pings = [
        AisPing(mmsi=2, vessel_id="V02", timestamp=t0, lat=19.0, lon=65.0, sog=14.0, cog=180.0, nav_status=0),
        AisPing(mmsi=2, vessel_id="V02", timestamp=t1, lat=17.0, lon=65.0, sog=14.0, cog=180.0, nav_status=0),
    ]
    track = VesselTrack(vessel_id="V02", pings=pings, total_distance_km=220.0)

    # Only ENTRY crossing detected
    crossings = [
        GatewayCrossingEvent(
            event_id="E3",
            vessel_id="V02",
            gateway_id="GATE_B",
            event_type=EventType.ENTRY,
            timestamp=t0 + timedelta(hours=1),
            latitude=18.0,
            longitude=65.0,
        )
    ]

    memory = MaritimeMemory()
    journeys = memory.build_journeys({"V02": track}, crossings)

    j = journeys["V02"]
    assert j.status == JourneyStatus.IN_REGION
    assert j.entry_gateway == "GATE_B"
    assert j.exit_gateway is None


def test_exit_only_journey():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=3)

    pings = [
        AisPing(mmsi=3, vessel_id="V03", timestamp=t0, lat=17.0, lon=65.0, sog=10.0, cog=180.0, nav_status=0),
        AisPing(mmsi=3, vessel_id="V03", timestamp=t1, lat=15.0, lon=65.0, sog=10.0, cog=180.0, nav_status=0),
    ]
    track = VesselTrack(vessel_id="V03", pings=pings, total_distance_km=220.0)

    crossings = [
        GatewayCrossingEvent(
            event_id="E4",
            vessel_id="V03",
            gateway_id="GATE_C",
            event_type=EventType.EXIT,
            timestamp=t1 - timedelta(minutes=15),
            latitude=15.8,
            longitude=65.0,
        )
    ]

    memory = MaritimeMemory()
    journeys = memory.build_journeys({"V03": track}, crossings)

    j = journeys["V03"]
    assert j.status == JourneyStatus.EXIT_ONLY_PARTIAL
    assert j.entry_gateway is None
    assert j.exit_gateway == "GATE_C"


def test_window_interior_journey():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    pings = [
        AisPing(mmsi=4, vessel_id="V04", timestamp=t0, lat=16.0, lon=65.0, sog=8.0, cog=90.0, nav_status=0),
        AisPing(mmsi=4, vessel_id="V04", timestamp=t0 + timedelta(hours=1), lat=16.0, lon=65.2, sog=8.0, cog=90.0, nav_status=0),
    ]
    track = VesselTrack(vessel_id="V04", pings=pings, total_distance_km=20.0)

    memory = MaritimeMemory()
    journeys = memory.build_journeys({"V04": track}, [])

    j = journeys["V04"]
    assert j.status == JourneyStatus.WINDOW_INTERIOR
    assert j.entry_gateway is None
    assert j.exit_gateway is None
