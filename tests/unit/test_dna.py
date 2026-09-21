"""Unit tests for src/ais/dna.py."""

from datetime import datetime, timedelta, timezone
import pytest

from src.ais.dna import BehavioralDNAExtractor
from src.ais.schemas import AisPing, VesselTrack


def make_track_for_dna(v_id: str, speed: float = 12.0, course: float = 90.0, n: int = 20):
    t0 = datetime(2024, 3, 15, 0, 0, tzinfo=timezone.utc)
    pings = [
        AisPing(
            mmsi=999,
            vessel_id=v_id,
            timestamp=t0 + timedelta(minutes=5 * i),
            lat=16.0 + 0.005 * i,
            lon=65.0 + 0.005 * i,
            sog=speed + 0.2 * (i % 3),
            cog=(course + (i % 5)) % 360.0,
            nav_status=0,
        )
        for i in range(n)
    ]
    return VesselTrack(vessel_id=v_id, pings=pings, total_distance_km=50.0)


def test_dna_extraction_and_symmetry():
    extractor = BehavioralDNAExtractor()
    t1 = make_track_for_dna("V_A", speed=14.0, course=180.0, n=25)
    t2 = make_track_for_dna("V_B", speed=10.0, course=45.0, n=25)

    p1 = extractor.extract_dna(t1)
    p2 = extractor.extract_dna(t2)

    assert p1.vessel_id == "V_A"
    assert p2.vessel_id == "V_B"
    assert len(p1.feature_vector) == 8
    assert p1.sample_count == 25
    assert p1.confidence >= 0.5

    # Test symmetric distance: compare(p1, p2) == compare(p2, p1)
    match_12 = extractor.compare_profiles(p1, p2)
    match_21 = extractor.compare_profiles(p2, p1)

    assert abs(match_12.mahalanobis_dist - match_21.mahalanobis_dist) < 1e-4
    assert abs(match_12.confidence_pct - match_21.confidence_pct) < 1e-4
    assert match_12.method in ["full_cov", "shrunk", "diagonal"]


def test_dna_small_sample_fallback():
    extractor = BehavioralDNAExtractor()
    # Only 2 pings (small n < 3 fallback to diagonal)
    t_small = make_track_for_dna("V_SMALL", speed=12.0, n=2)
    profile = extractor.extract_dna(t_small)
    assert profile.sample_count == 2
    assert profile.confidence < 0.4

    # Comparing should gracefully use diagonal fallback
    t_ref = make_track_for_dna("V_REF", speed=12.0, n=20)
    ref_profile = extractor.extract_dna(t_ref)

    match = extractor.compare_profiles(profile, ref_profile)
    assert match.method == "diagonal"
    assert match.mahalanobis_dist >= 0.0


def test_reidentify_post_gap():
    extractor = BehavioralDNAExtractor()
    t_tanker = make_track_for_dna("TANKER_1", speed=11.0, course=180.0, n=30)
    t_fast_cargo = make_track_for_dna("CARGO_1", speed=20.0, course=90.0, n=30)

    p_tanker = extractor.extract_dna(t_tanker)
    p_cargo = extractor.extract_dna(t_fast_cargo)
    profiles = {"TANKER_1": p_tanker, "CARGO_1": p_cargo}

    # Query track: behaves like tanker
    t_query = make_track_for_dna("MYSTERY_SHIP", speed=11.2, course=182.0, n=20)
    ranked = extractor.reidentify_post_gap(t_query, profiles)

    assert len(ranked) == 2
    # Top rank should be TANKER_1
    assert ranked[0].target_vessel_id == "TANKER_1"
    assert ranked[0].confidence_pct > ranked[1].confidence_pct
