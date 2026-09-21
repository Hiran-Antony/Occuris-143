"""Unit tests for src/ais/collective.py."""

from datetime import datetime, timedelta, timezone
import pytest

from src.ais.collective import CollectiveAnomalyDetector
from src.ais.schemas import (
    AisGap,
    AisPing,
    CollectiveAnomalyType,
    VesselTrack,
)


def test_coordinated_dark_detection():
    detector = CollectiveAnomalyDetector(
        dark_overlap_minutes=10.0,
        dark_proximity_nm=5.0,
    )
    t0 = datetime(2024, 3, 15, 6, 0, tzinfo=timezone.utc)

    # Two vessels with 25-minute overlapping gap starting within 1 NM of each other
    gap1 = AisGap(
        vessel_id="V1",
        gap_start=t0,
        gap_end=t0 + timedelta(minutes=25),
        duration_minutes=25.0,
        start_lat=16.5,
        start_lon=64.5,
        end_lat=16.5,
        end_lon=64.5,
    )
    gap2 = AisGap(
        vessel_id="V2",
        gap_start=t0 + timedelta(minutes=5),
        gap_end=t0 + timedelta(minutes=30),
        duration_minutes=25.0,
        start_lat=16.51,
        start_lon=64.51,  # ~0.8 NM away
        end_lat=16.51,
        end_lon=64.51,
    )

    t1 = VesselTrack(vessel_id="V1", pings=[], total_distance_km=10.0, gaps=[gap1])
    t2 = VesselTrack(vessel_id="V2", pings=[], total_distance_km=10.0, gaps=[gap2])

    events = detector.detect_collective_anomalies({"V1": t1, "V2": t2})
    dark_events = [e for e in events if e.anomaly_type == CollectiveAnomalyType.COORDINATED_DARK]

    assert len(dark_events) == 1
    ev = dark_events[0]
    assert "V1" in ev.vessel_cluster
    assert "V2" in ev.vessel_cluster
    assert ev.evidence["temporal_overlap_minutes"] == 20.0
    assert ev.evidence["separation_distance_nm"] < 2.0


def test_rendezvous_detection():
    detector = CollectiveAnomalyDetector(
        rendezvous_distance_m=500.0,
        rendezvous_max_sog_kn=3.0,
        rendezvous_min_duration_min=20.0,
    )
    t0 = datetime(2024, 3, 15, 8, 0, tzinfo=timezone.utc)

    # 4 pings every 10 min (30 min duration), separation ~200m, SOG 1.5 kn
    pings1 = [
        AisPing(mmsi=1, vessel_id="V_R1", timestamp=t0 + timedelta(minutes=10 * i), lat=17.0, lon=65.0, sog=1.5, cog=0.0, nav_status=0)
        for i in range(4)
    ]
    pings2 = [
        AisPing(mmsi=2, vessel_id="V_R2", timestamp=t0 + timedelta(minutes=10 * i), lat=17.001, lon=65.001, sog=1.2, cog=0.0, nav_status=0)
        for i in range(4)
    ]

    t1 = VesselTrack(vessel_id="V_R1", pings=pings1, total_distance_km=2.0)
    t2 = VesselTrack(vessel_id="V_R2", pings=pings2, total_distance_km=2.0)

    events = detector.detect_collective_anomalies({"V_R1": t1, "V_R2": t2})
    rdvz = [e for e in events if e.anomaly_type == CollectiveAnomalyType.RENDEZVOUS]

    assert len(rdvz) == 1
    assert "V_R1" in rdvz[0].vessel_cluster
    assert "V_R2" in rdvz[0].vessel_cluster
    assert rdvz[0].evidence["duration_minutes"] >= 20.0
