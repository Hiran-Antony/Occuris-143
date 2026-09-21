"""
Module 6 — Integration Test: Full Module 5 → Module 6 Pipeline
Tests the complete chain from Module 5 evidence bundles through the 6-stage
verification pipeline, asserting ground-truth labels.
MVP DoD: one normal + one gapped + one spoofed vessel correctly labelled.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    AisGap,
    AisPing,
    AisState,
    BehaviourAssessment,
    BehaviourStatus,
    CandidateDarkPath,
    CaseContextV1,
    DarkPathHypothesis,
    EvidenceBundleV1,
    ExplanationFactor,
    FactorSupportStatus,
    ReachabilityVerdict,
    TransitAnalysis,
    ExpectedTimeBasis,
    VesselJourney,
    VesselTrack,
)
from src.verification.pipeline import VerificationPipeline, load_verification_config


@pytest.fixture
def config():
    return load_verification_config()


@pytest.fixture
def pipeline(config):
    return VerificationPipeline(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def context(base_time):
    return CaseContextV1(
        case_id="case_01",
        origin_zones=[{
            "type": "Polygon",
            "coordinates": [[[52.2, 14.0], [54.0, 14.0], [54.0, 15.6], [52.2, 15.6], [52.2, 14.0]]],
        }],
        release_window_start=base_time - timedelta(hours=24),
        release_window_end=base_time,
        sar_acquisition_time=base_time,
        spill_center={"lat": 14.8, "lon": 53.1},
    )


def _make_normal_bundle(base_time):
    journey = VesselJourney(
        vessel_id="V_NORMAL",
        entry_time=base_time - timedelta(hours=10),
        exit_time=base_time + timedelta(hours=2),
    )
    transit = TransitAnalysis(
        actual_duration_h=12.0,
        expected_duration_h=11.5,
        delay_h=0.5,
        z_score=0.3,
        expected_basis=ExpectedTimeBasis.HISTORICAL,
    )
    assessment = BehaviourAssessment(
        vessel_id="V_NORMAL",
        status=BehaviourStatus.NORMAL_TRANSIT,
        explanations=[
            ExplanationFactor(factor="AIS_GAP", status=FactorSupportStatus.NOT_SUPPORTED,
                              detail="Continuous AIS"),
        ],
    )
    return EvidenceBundleV1(
        case_id="case_01", vessel_id="V_NORMAL",
        journey=journey, transit_analysis=transit,
        behaviour_assessment=assessment,
    )


def _make_gapped_bundle(base_time):
    journey = VesselJourney(
        vessel_id="V_GAP",
        entry_time=base_time - timedelta(hours=10),
        exit_time=base_time + timedelta(hours=5),
    )
    gap = AisGap(
        vessel_id="V_GAP",
        gap_start=base_time - timedelta(hours=5),
        gap_end=base_time - timedelta(hours=4),
        duration_minutes=60.0,
        start_lat=15.5, start_lon=54.0,
        end_lat=15.6, end_lon=54.2,
    )
    assessment = BehaviourAssessment(
        vessel_id="V_GAP",
        status=BehaviourStatus.POTENTIAL_UNEXPLAINED_DELAY,
        explanations=[
            ExplanationFactor(factor="AIS_GAP", status=FactorSupportStatus.SUPPORTED,
                              detail="60 min gap detected"),
        ],
    )
    return EvidenceBundleV1(
        case_id="case_01", vessel_id="V_GAP",
        journey=journey, ais_gaps=[gap],
        behaviour_assessment=assessment,
    )


def _make_normal_track(base_time):
    pings = []
    lat, lon = 16.0, 65.0
    for i in range(30):
        pings.append(AisPing(
            mmsi=477001001, vessel_id="V_NORMAL",
            timestamp=base_time - timedelta(hours=10) + timedelta(minutes=10 * i),
            lat=round(lat, 5), lon=round(lon, 5), sog=12.0, cog=90.0,
        ))
        lon += 0.02
    return VesselTrack(vessel_id="V_NORMAL", pings=pings)


def _make_gapped_track(base_time):
    pings = []
    lat, lon = 15.5, 54.0
    for i in range(40):
        t = base_time - timedelta(hours=10) + timedelta(minutes=10 * i)
        if 18 <= i <= 23:  # Skip pings to create gap
            continue
        pings.append(AisPing(
            mmsi=477003003, vessel_id="V_GAP",
            timestamp=t,
            lat=round(lat, 5), lon=round(lon, 5), sog=11.0, cog=85.0,
        ))
        lon += 0.015
    return VesselTrack(vessel_id="V_GAP", pings=pings)


def _make_spoofed_bundle(base_time):
    journey = VesselJourney(
        vessel_id="V_SPOOF",
        entry_time=base_time - timedelta(hours=10),
        exit_time=base_time + timedelta(hours=2),
    )
    return EvidenceBundleV1(
        case_id="case_01", vessel_id="V_SPOOF",
        journey=journey,
    )


def _make_spoofed_track(base_time):
    pings = []
    lat, lon = 16.0, 65.0
    for i in range(15):
        t = base_time - timedelta(hours=10) + timedelta(minutes=10 * i)
        if i == 8:
            lat += 5.0  # Teleport 550 km
        pings.append(AisPing(
            mmsi=477009009, vessel_id="V_SPOOF",
            timestamp=t, lat=round(lat, 5), lon=round(lon, 5), sog=12.0, cog=90.0,
        ))
    return VesselTrack(vessel_id="V_SPOOF", pings=pings)


class TestModule6Integration:
    def test_normal_vessel(self, pipeline, base_time, context):
        """Normal vessel should have NORMAL AIS state and high integrity."""
        bundle = _make_normal_bundle(base_time)
        track = _make_normal_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        assert result.ais_state == AisState.NORMAL
        assert result.integrity_score > 0.7
        assert result.module6_version == "6.0.0"
        print(f"\n[MVP DoD] V_NORMAL: state={result.ais_state.value}, "
              f"integrity={result.integrity_score:.3f}")

    def test_gapped_vessel(self, pipeline, base_time, context):
        """Gapped vessel should have AIS_GAP_DARK or AMBIGUOUS state."""
        bundle = _make_gapped_bundle(base_time)
        track = _make_gapped_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        assert result.ais_state in [AisState.AIS_GAP_DARK, AisState.AMBIGUOUS]
        assert result.continuity is not None
        assert result.continuity.total_gaps >= 1

        # Print reachability distances for DoD
        if result.reachability and result.reachability.round_trip_dark_checks:
            for check in result.reachability.round_trip_dark_checks:
                print(f"\n[MVP DoD] V_GAP reachability: "
                      f"d1={check.get('d1_km', 'N/A')}km, "
                      f"d2={check.get('d2_km', 'N/A')}km, "
                      f"required={check.get('required_kn', 'N/A')}kn, "
                      f"limit={check.get('limit_kn', 'N/A')}kn, "
                      f"verdict={check.get('verdict', 'N/A')}")

    def test_spoofed_vessel(self, pipeline, base_time, context):
        """Spoofed vessel (teleport jump) should have REPORTING_ANOMALY state."""
        bundle = _make_spoofed_bundle(base_time)
        track = _make_spoofed_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        assert result.ais_state == AisState.REPORTING_ANOMALY
        assert result.kinematic is not None
        assert result.kinematic.anomalous_pings > 0
        assert result.integrity_score < 0.5

        print(f"\n[MVP DoD] V_SPOOF: state={result.ais_state.value}, "
              f"integrity={result.integrity_score:.3f}")
        if result.reachability:
            print(f"[MVP DoD] V_SPOOF reachability: "
                  f"inter_ping_violations={result.reachability.inter_ping_violations}")

    def test_full_case_run(self, pipeline, base_time, context):
        """Run full case with multiple vessels (normal + gapped + spoofed)."""
        bundles = [
            _make_normal_bundle(base_time),
            _make_gapped_bundle(base_time),
            _make_spoofed_bundle(base_time),
        ]
        tracks = {
            "V_NORMAL": _make_normal_track(base_time),
            "V_GAP": _make_gapped_track(base_time),
            "V_SPOOF": _make_spoofed_track(base_time),
        }
        results = pipeline.run_case(bundles, context, tracks)
        assert len(results) == 3

        # Verify each vessel got processed
        vessel_ids = {r.vessel_id for r in results}
        assert "V_NORMAL" in vessel_ids
        assert "V_GAP" in vessel_ids
        assert "V_SPOOF" in vessel_ids

    def test_output_bundle_structure(self, pipeline, base_time, context):
        """Verify Module6VerificationBundleV1 has all required fields."""
        bundle = _make_normal_bundle(base_time)
        track = _make_normal_track(base_time)
        result = pipeline.run(bundle, context, track=track)

        assert result.schema_version == "1.0.0"
        assert result.case_id == "case_01"
        assert result.vessel_id == "V_NORMAL"
        assert result.window is not None
        assert result.continuity is not None
        assert result.kinematic is not None
        assert result.integrity_method == "bayesian_odds_lr"
        assert 0.0 <= result.integrity_score <= 1.0
        assert len(result.integrity_interval) == 2
        assert result.source_mode is not None
        assert result.generated_at is not None
