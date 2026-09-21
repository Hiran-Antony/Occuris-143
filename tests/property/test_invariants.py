"""Property-based mathematical and architectural invariants."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from src.api.maritime import MaritimeEngineState
from src.ais.crossing import CrossingDetector
from src.ais.gateways import get_default_gateways, GatewayManager
from src.ais.dna import BehavioralDNAExtractor
from src.ais.dark_path import DarkPathReconstructor
from src.ais.schemas import AisPing, AisGap, VesselTrack

ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_CSV = ROOT / "data" / "raw" / "synthetic" / "module5_demo.csv"


def test_property_interpolation_ratio_bounded():
    """Invariant 1: All interpolation ratios must be strictly within [0.0, 1.0]."""
    gw_mgr = GatewayManager(get_default_gateways())
    detector = CrossingDetector(gateway_manager=gw_mgr)

    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    for dx in [0.1, 0.5, 1.0, 2.0]:
        pings = [
            AisPing(mmsi=1, vessel_id="V_PROP", timestamp=t0, lat=18.0, lon=62.5, sog=12.0, cog=90.0, nav_status=0),
            AisPing(mmsi=1, vessel_id="V_PROP", timestamp=t0 + timedelta(minutes=30), lat=18.0, lon=62.5 + dx, sog=12.0, cog=90.0, nav_status=0),
        ]
        track = VesselTrack(vessel_id="V_PROP", pings=pings, total_distance_km=dx * 100.0)
        events = detector.detect_crossings(track)
        for ev in events:
            assert 0.0 <= ev.interpolation_ratio <= 1.0


def test_property_dna_distance_symmetry_and_non_negativity():
    """Invariant 2: Mahalanobis distance D(p1, p2) >= 0 and D(p1, p2) == D(p2, p1)."""
    extractor = BehavioralDNAExtractor()
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)

    for i in range(5):
        t1 = VesselTrack(
            vessel_id=f"V_INV_{i}",
            pings=[
                AisPing(mmsi=i, vessel_id=f"V_INV_{i}", timestamp=t0 + timedelta(minutes=5 * k), lat=16.0 + 0.01 * k, lon=65.0, sog=10.0 + k % 3, cog=45.0, nav_status=0)
                for k in range(15)
            ],
            total_distance_km=30.0,
        )
        t2 = VesselTrack(
            vessel_id=f"V_REF_{i}",
            pings=[
                AisPing(mmsi=i + 10, vessel_id=f"V_REF_{i}", timestamp=t0 + timedelta(minutes=5 * k), lat=17.0 + 0.01 * k, lon=66.0, sog=14.0 + k % 2, cog=180.0, nav_status=0)
                for k in range(15)
            ],
            total_distance_km=30.0,
        )

        p1 = extractor.extract_dna(t1)
        p2 = extractor.extract_dna(t2)

        m12 = extractor.compare_profiles(p1, p2)
        m21 = extractor.compare_profiles(p2, p1)

        assert m12.mahalanobis_dist >= 0.0
        assert m21.mahalanobis_dist >= 0.0
        assert abs(m12.mahalanobis_dist - m21.mahalanobis_dist) < 1e-4
        assert abs(m12.confidence_pct - m21.confidence_pct) < 1e-4


def test_property_dark_path_probability_normalization():
    """Invariant 3: Sum of candidate path probabilities in dark path hypothesis equals 1.0."""
    reconstructor = DarkPathReconstructor()
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)

    for dur_min in [30.0, 60.0, 120.0]:
        gap = AisGap(
            vessel_id="V_HYP",
            gap_start=t0,
            gap_end=t0 + timedelta(minutes=dur_min),
            duration_minutes=dur_min,
            start_lat=15.0,
            start_lon=64.0,
            end_lat=15.2,
            end_lon=64.2,
        )
        track = VesselTrack(vessel_id="V_HYP", pings=[], total_distance_km=20.0, gaps=[gap])
        hypotheses = reconstructor.reconstruct_hypotheses(track)

        assert len(hypotheses) == 1
        prob_sum = sum(p.probability for p in hypotheses[0].candidate_paths)
        assert abs(prob_sum - 1.0) < 1e-3

        for p in hypotheses[0].candidate_paths:
            # First waypoint matches gap start
            assert abs(p.waypoints[0][0] - gap.start_lon) < 1e-4
            assert abs(p.waypoints[0][1] - gap.start_lat) < 1e-4
            # Last waypoint matches gap end
            assert abs(p.waypoints[-1][0] - gap.end_lon) < 1e-4
            assert abs(p.waypoints[-1][1] - gap.end_lat) < 1e-4


def test_property_deterministic_build_hashes():
    """Invariant 4: Running full engine with identical seed yields identical output_hash."""
    e1 = MaritimeEngineState()
    e1.load_and_process(DEMO_CSV, seed=123)

    e2 = MaritimeEngineState()
    e2.load_and_process(DEMO_CSV, seed=123)

    assert e1.output_hash == e2.output_hash
    assert e1.build_id == e2.build_id
