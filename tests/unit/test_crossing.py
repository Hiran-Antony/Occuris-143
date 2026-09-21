"""Unit tests for src/ais/crossing.py and src/ais/gateways.py."""

from datetime import datetime, timedelta, timezone
import pytest
from shapely.geometry import Polygon

from src.ais.gateways import (
    GatewayCorridor,
    GatewayManager,
    gateways_to_geojson,
    get_default_gateways,
)
from src.ais.crossing import CrossingDetector
from src.ais.schemas import EventType, AisPing, VesselTrack


def make_corridor_box(gw_id: str, min_lon: float, max_lon: float, min_lat: float, max_lat: float, orientation="west"):
    poly_coords = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]
    return GatewayCorridor(
        gateway_id=gw_id,
        name=f"Test Gateway {gw_id}",
        orientation=orientation,
        entry_side="west",
        exit_side="east",
        geometry_geojson={"type": "Polygon", "coordinates": [poly_coords]},
    )


def test_gateways_to_geojson():
    gws = get_default_gateways()
    geojson = gateways_to_geojson(gws)
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == len(gws)
    assert "geometry" in geojson["features"][0]
    assert "properties" in geojson["features"][0]


def test_crossing_exact_linear_interpolation():
    gw = make_corridor_box("TEST_GW", 64.9, 65.1, 10.0, 20.0, orientation="west")
    mgr = GatewayManager([gw])
    detector = CrossingDetector(gateway_manager=mgr)

    t1 = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2024, 3, 15, 10, 10, 0, tzinfo=timezone.utc)  # 600s later

    # Vessel moves from lon 64.0 (outside west) to 66.0 (outside east) at lat 15.0
    # Intersection with west entry line at lon 64.9:
    # r = (64.9 - 64.0) / (66.0 - 64.0) = 0.9 / 2.0 = 0.45
    # Expected crossing time: t1 + 0.45 * 600s = t1 + 270s = 10:04:30
    p1 = AisPing(
        mmsi=123,
        vessel_id="V_CROSS",
        timestamp=t1,
        lat=15.0,
        lon=64.0,
        sog=10.0,
        cog=90.0,
        nav_status=0,
    )
    p2 = AisPing(
        mmsi=123,
        vessel_id="V_CROSS",
        timestamp=t2,
        lat=15.0,
        lon=66.0,
        sog=10.0,
        cog=90.0,
        nav_status=0,
    )

    track = VesselTrack(
        vessel_id="V_CROSS",
        pings=[p1, p2],
        total_distance_km=200.0,
    )

    events = detector.detect_crossings(track)
    assert len(events) >= 1
    entry_ev = next((e for e in events if e.event_type == EventType.ENTRY), None)
    assert entry_ev is not None
    assert entry_ev.gateway_id == "TEST_GW"
    assert entry_ev.latitude == 15.0
    assert abs(entry_ev.longitude - 64.9) < 1e-4

    # Verify interpolation ratio
    expected_sec = 270.0
    actual_sec = (entry_ev.timestamp - t1).total_seconds()
    assert abs(actual_sec - expected_sec) < 1.0


def test_duplicate_event_suppression():
    gw = make_corridor_box("TEST_GW", 64.9, 65.1, 10.0, 20.0)
    mgr = GatewayManager([gw])
    detector = CrossingDetector(gateway_manager=mgr)

    t0 = datetime(2024, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    # Ping crossing boundary, then immediate follow-up ping crossing back within duplicate window
    pings = [
        AisPing(mmsi=1, vessel_id="V_DUP", timestamp=t0, lat=15.0, lon=64.8, sog=10.0, cog=90.0, nav_status=0),
        AisPing(mmsi=1, vessel_id="V_DUP", timestamp=t0 + timedelta(seconds=60), lat=15.0, lon=65.2, sog=10.0, cog=90.0, nav_status=0),
        AisPing(mmsi=1, vessel_id="V_DUP", timestamp=t0 + timedelta(seconds=120), lat=15.0, lon=65.3, sog=10.0, cog=90.0, nav_status=0),
    ]
    track = VesselTrack(vessel_id="V_DUP", pings=pings, total_distance_km=50.0)
    events = detector.detect_crossings(track)

    # Should have exactly 1 ENTRY event, not duplicated
    entries = [e for e in events if e.event_type == EventType.ENTRY]
    assert len(entries) == 1
