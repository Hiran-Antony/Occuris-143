"""Unit tests for src/ais/track_builder.py."""

from datetime import datetime, timedelta, timezone
import pytest

from src.ais.track_builder import (
    TrackBuilder,
    geodesic_distance_km,
    geodesic_distance_nm,
)
from src.ais.schemas import AISContinuity, AisPing


def test_geodesic_distance():
    # 1 degree lat along equator is approx 111.19 km (~60 NM)
    d_km = geodesic_distance_km(0.0, 0.0, 1.0, 0.0)
    assert 110.0 < d_km < 112.0

    d_nm = geodesic_distance_nm(0.0, 0.0, 1.0, 0.0)
    assert 59.0 < d_nm < 61.0


def test_build_tracks_continuous():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    pings = [
        AisPing(
            mmsi=111,
            vessel_id="V01",
            vessel_name="SHIP 1",
            timestamp=t0 + timedelta(minutes=10 * i),
            lat=18.0 + 0.01 * i,
            lon=65.0 + 0.01 * i,
            sog=12.0,
            cog=45.0,
            nav_status=0,
        )
        for i in range(5)
    ]

    builder = TrackBuilder(ais_gap_threshold_min=15.0)
    tracks = builder.build_tracks(pings)

    assert "V01" in tracks
    track = tracks["V01"]
    assert len(track.pings) == 5
    assert track.total_distance_km > 0
    assert len(track.gaps) == 0
    assert track.ais_continuity == AISContinuity.CONTINUOUS


def test_build_tracks_with_gap():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    pings = [
        AisPing(
            mmsi=222,
            vessel_id="V02",
            vessel_name="SHIP 2",
            timestamp=t0,
            lat=18.0,
            lon=65.0,
            sog=12.0,
            cog=45.0,
            nav_status=0,
        ),
        # Gap of 45 minutes (> 15 min threshold)
        AisPing(
            mmsi=222,
            vessel_id="V02",
            vessel_name="SHIP 2",
            timestamp=t0 + timedelta(minutes=45),
            lat=18.05,
            lon=65.05,
            sog=12.0,
            cog=45.0,
            nav_status=0,
        ),
    ]

    builder = TrackBuilder(ais_gap_threshold_min=15.0)
    tracks = builder.build_tracks(pings)

    track = tracks["V02"]
    assert len(track.gaps) == 1
    assert track.gaps[0].duration_minutes == 45.0
    assert track.ais_continuity == AISContinuity.GAP_DETECTED


def test_get_state_at_time():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    pings = [
        AisPing(
            mmsi=333,
            vessel_id="V03",
            vessel_name="SHIP 3",
            timestamp=t0 + timedelta(minutes=10 * i),
            lat=15.0 + 0.01 * i,
            lon=64.0,
            sog=10.0,
            cog=0.0,
            nav_status=0,
        )
        for i in range(3)
    ]
    builder = TrackBuilder()
    tracks = builder.build_tracks(pings)
    track = tracks["V03"]

    # Target between ping 0 and 1
    state = TrackBuilder.get_state_at_time(track, t0 + timedelta(minutes=5))
    assert state is not None
    assert state["vessel_id"] == "V03"
    assert state["lat"] == 15.0  # Last known ping before t0 + 5 min is ping 0
    assert len(state["trail"]) == 1

    # Target before any ping
    state_prior = TrackBuilder.get_state_at_time(track, t0 - timedelta(minutes=10))
    assert state_prior is None
