"""Unit tests for src/ais/traffic.py."""

from datetime import datetime, timedelta, timezone
import pytest

from src.ais.traffic import TrafficAnalyzer
from src.ais.schemas import AisPing, TrafficLevel


def test_empty_traffic():
    analyzer = TrafficAnalyzer(bin_duration_minutes=60, percentile_threshold=75.0)
    bins = analyzer.compute_density_bins([])
    assert bins == []


def test_traffic_density_bins():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    records = []

    # Hour 1: 5 vessels (High)
    for v in range(5):
        records.append(
            AisPing(mmsi=100 + v, vessel_id=f"V{v}", timestamp=t0 + timedelta(minutes=15), lat=16.0, lon=65.0, sog=10.0, cog=90.0, nav_status=0)
        )

    # Hour 2: 2 vessels (Normal)
    for v in range(2):
        records.append(
            AisPing(mmsi=200 + v, vessel_id=f"V{v}", timestamp=t0 + timedelta(minutes=75), lat=16.0, lon=65.0, sog=10.0, cog=90.0, nav_status=0)
        )

    # Hour 3: 1 vessel (Low)
    records.append(
        AisPing(mmsi=300, vessel_id="V0", timestamp=t0 + timedelta(minutes=135), lat=16.0, lon=65.0, sog=10.0, cog=90.0, nav_status=0)
    )

    analyzer = TrafficAnalyzer(bin_duration_minutes=60, percentile_threshold=75.0)
    bins = analyzer.compute_density_bins(records)

    assert len(bins) >= 3
    assert bins[0].vessel_count == 5
    assert bins[0].percentile_class == "HIGH"
    assert bins[2].vessel_count == 1
    assert bins[2].percentile_class == "LOW"


def test_get_traffic_at_time():
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    records = [
        AisPing(mmsi=i, vessel_id=f"V{i}", timestamp=t0 + timedelta(minutes=10), lat=16.0, lon=65.0, sog=10.0, cog=90.0, nav_status=0)
        for i in range(5)
    ]

    analyzer = TrafficAnalyzer(bin_duration_minutes=60, percentile_threshold=75.0)
    analyzer.compute_density_bins(records)

    query_res = analyzer.get_traffic_at_time(records, t0 + timedelta(minutes=30))
    assert query_res["vessel_count"] == 5
    assert query_res["level"] == TrafficLevel.HIGH
    assert query_res["is_high_density"] is True
