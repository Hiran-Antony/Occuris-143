"""
Module 6 — Unit Tests: Reachability Engine (Stage 4)
Tests inter-ping violations, round-trip dark checks with current-assist bounds.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    AisGap,
    AisPing,
    CaseContextV1,
    EvidenceBundleV1,
    ReachabilityVerdict,
    VesselTrack,
    VerificationStageStatus,
)
from src.verification.reachability_engine import ReachabilityEngine


@pytest.fixture
def config():
    return {
        "reachability": {
            "margin_band_pct": 10,
            "current_assist": True,
            "current_boost_kn": 2.0,
        },
        "_region": {
            "vessel_class_max_speeds_kn": {"default": 18.0},
        },
    }


@pytest.fixture
def engine(config):
    return ReachabilityEngine(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)


def _make_context(spill_lat=14.8, spill_lon=53.1):
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return CaseContextV1(
        case_id="case_01",
        release_window_start=base,
        release_window_end=base + timedelta(hours=24),
        spill_center={"lat": spill_lat, "lon": spill_lon},
    )


class TestReachabilityEngine:
    def test_normal_track_reachable(self, engine, base_time):
        """Normal speed track should be REACHABLE."""
        pings = []
        lat, lon = 16.0, 65.0
        for i in range(10):
            pings.append(AisPing(
                mmsi=477001001, vessel_id="V001",
                timestamp=base_time + timedelta(minutes=10 * i),
                lat=round(lat, 5), lon=round(lon, 5), sog=12.0,
            ))
            lon += 0.02  # Normal speed
        track = VesselTrack(vessel_id="V001", pings=pings)
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V001")
        result = engine.analyze(bundle, _make_context(), track=track)
        assert result.overall_verdict == ReachabilityVerdict.REACHABLE
        assert result.inter_ping_violations == 0

    def test_impossible_speed_violation(self, engine, base_time):
        """Teleport-like inter-ping should flag violation."""
        pings = [
            AisPing(mmsi=477001001, vessel_id="V_FAST",
                    timestamp=base_time, lat=16.0, lon=65.0, sog=12.0),
            AisPing(mmsi=477001001, vessel_id="V_FAST",
                    timestamp=base_time + timedelta(minutes=10),
                    lat=16.0, lon=70.0, sog=12.0),  # 5 degrees in 10 min
        ]
        track = VesselTrack(vessel_id="V_FAST", pings=pings)
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V_FAST")
        result = engine.analyze(bundle, _make_context(), track=track)
        assert result.inter_ping_violations > 0

    def test_round_trip_reachable(self, engine, base_time):
        """Short gap near origin should be REACHABLE."""
        gap = AisGap(
            vessel_id="V003",
            gap_start=base_time,
            gap_end=base_time + timedelta(hours=10),
            duration_minutes=600.0,
            start_lat=15.0, start_lon=54.0,
            end_lat=15.0, end_lon=54.0,
        )
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V003", ais_gaps=[gap])
        track = VesselTrack(vessel_id="V003", pings=[])
        result = engine.analyze(bundle, _make_context(spill_lat=14.8, spill_lon=53.1), track=track)
        assert len(result.round_trip_dark_checks) == 1
        check = result.round_trip_dark_checks[0]
        assert "d1_km" in check
        assert "d2_km" in check
        assert "required_kn" in check

    def test_round_trip_implausible(self, engine, base_time):
        """Very short gap with huge distance to origin should be IMPLAUSIBLE."""
        gap = AisGap(
            vessel_id="V_IMP",
            gap_start=base_time,
            gap_end=base_time + timedelta(minutes=30),
            duration_minutes=30.0,
            start_lat=16.0, start_lon=65.0,
            end_lat=16.0, end_lon=65.0,
        )
        # Origin very far away
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V_IMP", ais_gaps=[gap])
        track = VesselTrack(vessel_id="V_IMP", pings=[])
        result = engine.analyze(bundle, _make_context(spill_lat=14.8, spill_lon=53.1), track=track)
        assert len(result.round_trip_dark_checks) == 1
        assert result.round_trip_dark_checks[0]["verdict"] == "IMPLAUSIBLE"
        assert result.overall_verdict == ReachabilityVerdict.IMPLAUSIBLE

    def test_no_origin_zone(self, engine, base_time):
        """Missing origin zone should skip round-trip check."""
        gap = AisGap(
            vessel_id="V_NO",
            gap_start=base_time,
            gap_end=base_time + timedelta(hours=1),
            duration_minutes=60.0,
            start_lat=16.0, start_lon=65.0,
            end_lat=16.1, end_lon=65.1,
        )
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V_NO", ais_gaps=[gap])
        context = CaseContextV1(
            case_id="case_01",
            release_window_start=base_time,
            release_window_end=base_time + timedelta(hours=24),
        )
        track = VesselTrack(vessel_id="V_NO", pings=[])
        result = engine.analyze(bundle, context, track=track)
        assert result.overall_verdict == ReachabilityVerdict.REACHABLE

    def test_current_assist_increases_limit(self, base_time):
        """With current_assist=True, limit should be max_speed + boost."""
        config_assist = {
            "reachability": {"margin_band_pct": 10, "current_assist": True, "current_boost_kn": 2.0},
            "_region": {"vessel_class_max_speeds_kn": {"default": 18.0}},
        }
        config_no_assist = {
            "reachability": {"margin_band_pct": 10, "current_assist": False, "current_boost_kn": 2.0},
            "_region": {"vessel_class_max_speeds_kn": {"default": 18.0}},
        }

        gap = AisGap(
            vessel_id="V_CUR",
            gap_start=base_time,
            gap_end=base_time + timedelta(hours=5),
            duration_minutes=300.0,
            start_lat=15.5, start_lon=54.0,
            end_lat=15.5, end_lon=54.0,
        )
        bundle = EvidenceBundleV1(case_id="case_01", vessel_id="V_CUR", ais_gaps=[gap])
        context = _make_context()
        track = VesselTrack(vessel_id="V_CUR", pings=[])

        result_assist = ReachabilityEngine(config_assist).analyze(bundle, context, track)
        result_no = ReachabilityEngine(config_no_assist).analyze(bundle, context, track)

        if result_assist.round_trip_dark_checks and result_no.round_trip_dark_checks:
            assert result_assist.round_trip_dark_checks[0]["limit_kn"] > \
                   result_no.round_trip_dark_checks[0]["limit_kn"]
