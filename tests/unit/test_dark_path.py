"""Unit tests for src/ais/dark_path.py."""

from datetime import datetime, timedelta, timezone
import pytest

from src.ais.dark_path import DarkPathReconstructor
from src.ais.schemas import AisGap, VesselTrack


def test_dark_path_reconstruction():
    reconstructor = DarkPathReconstructor(max_vessel_speed_knots=18.0)
    t0 = datetime(2024, 3, 15, 4, 0, tzinfo=timezone.utc)

    # 1 hour gap between 15.0N, 64.0E and 15.2N, 64.2E
    # Distance is ~18 NM, which is reachable within 1 hour at 18 kn
    gap = AisGap(
        vessel_id="V_DARK_TEST",
        gap_start=t0,
        gap_end=t0 + timedelta(hours=1),
        duration_minutes=60.0,
        start_lat=15.0,
        start_lon=64.0,
        end_lat=15.2,
        end_lon=64.2,
    )
    track = VesselTrack(
        vessel_id="V_DARK_TEST",
        pings=[],
        total_distance_km=30.0,
        gaps=[gap],
    )

    hypotheses = reconstructor.reconstruct_hypotheses(track)

    assert len(hypotheses) == 1
    hyp = hypotheses[0]
    assert hyp.vessel_id == "V_DARK_TEST"
    assert len(hyp.candidate_paths) >= 1

    # Check probabilities sum to ~1.0
    total_prob = sum(p.probability for p in hyp.candidate_paths)
    assert abs(total_prob - 1.0) < 1e-3

    # Check path waypoints are non-empty
    direct_path = hyp.candidate_paths[0]
    assert len(direct_path.waypoints) >= 2


def test_dark_path_unreachable_gap():
    reconstructor = DarkPathReconstructor(max_vessel_speed_knots=18.0)
    t0 = datetime(2024, 3, 15, 4, 0, tzinfo=timezone.utc)

    # 15-minute gap but 100 NM apart (physically impossible speed > 400 kn)
    gap = AisGap(
        vessel_id="V_SUPERSONIC",
        gap_start=t0,
        gap_end=t0 + timedelta(minutes=15),
        duration_minutes=15.0,
        start_lat=15.0,
        start_lon=64.0,
        end_lat=16.6,  # ~100 NM north
        end_lon=64.0,
    )
    track = VesselTrack(
        vessel_id="V_SUPERSONIC",
        pings=[],
        total_distance_km=180.0,
        gaps=[gap],
    )

    hypotheses = reconstructor.reconstruct_hypotheses(track)
    assert len(hypotheses) == 1
    # Candidate paths generated carry low probability or fallback
    assert len(hypotheses[0].candidate_paths) >= 1
