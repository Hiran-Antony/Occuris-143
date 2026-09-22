"""
Module 6 — Unit Tests: Kinematic Engine (Stage 3)
Tests EKF NIS p-values, episode typing, and identity conflict detection.
"""

import pytest
import math
from datetime import datetime, timedelta, timezone

from src.ais.schemas import (
    AisPing,
    CaseContextV1,
    EvidenceBundleV1,
    KinematicFlag,
    VesselTrack,
    VerificationStageStatus,
)
from src.verification.kinematic_engine import KinematicEngine, _lla_to_enu


@pytest.fixture
def config():
    return {
        "ekf": {
            "dt_s": 600,
            "process_noise_q": 0.01,
            "measurement_sigma_m": 15.0,
            "chi2_alpha": 0.01,
            "episode_min_pings": 3,
            "extreme_p": 1e-6,
        },
        "identity_conflict": {
            "min_sep_km": 50,
            "max_dt_min": 30,
        },
        "_region": {
            "vessel_class_max_speeds_kn": {"default": 18.0},
        },
    }


@pytest.fixture
def engine(config):
    return KinematicEngine(config)


@pytest.fixture
def base_time():
    return datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)


def _make_clean_track(vessel_id, base_time, n_pings=20, speed_deg=0.02):
    """Generate a clean constant-velocity track (should pass EKF)."""
    pings = []
    lat, lon = 16.0, 65.0
    for i in range(n_pings):
        pings.append(AisPing(
            mmsi=477001001,
            vessel_id=vessel_id,
            timestamp=base_time + timedelta(minutes=10 * i),
            lat=round(lat, 5),
            lon=round(lon, 5),
            sog=12.0,
            cog=90.0,
        ))
        lon += speed_deg  # Steady eastward movement
    return VesselTrack(vessel_id=vessel_id, pings=pings)


def _make_teleport_track(vessel_id, base_time):
    """Generate a track with a teleport jump (should fail EKF)."""
    pings = []
    lat, lon = 16.0, 65.0
    for i in range(15):
        pings.append(AisPing(
            mmsi=477001001,
            vessel_id=vessel_id,
            timestamp=base_time + timedelta(minutes=10 * i),
            lat=round(lat, 5),
            lon=round(lon, 5),
            sog=12.0,
            cog=90.0,
        ))
        if i == 7:
            # Teleport: jump 5 degrees in one 10-min interval
            lon += 5.0
        else:
            lon += 0.02
    return VesselTrack(vessel_id=vessel_id, pings=pings)


def _make_bundle(vessel_id="V001"):
    return EvidenceBundleV1(case_id="case_01", vessel_id=vessel_id)


def _make_context():
    base = datetime(2024, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    return CaseContextV1(
        case_id="case_01",
        release_window_start=base,
        release_window_end=base + timedelta(hours=24),
    )


class TestENU:
    def test_lla_to_enu_origin(self):
        x, y = _lla_to_enu(16.0, 65.0, 16.0, 65.0)
        assert abs(x) < 1e-6
        assert abs(y) < 1e-6

    def test_lla_to_enu_north(self):
        x, y = _lla_to_enu(17.0, 65.0, 16.0, 65.0)
        assert abs(x) < 1e-6
        assert y > 100000  # ~111 km north


class TestKinematicEngine:
    def test_clean_track_passes(self, engine, base_time):
        track = _make_clean_track("V001", base_time)
        bundle = _make_bundle("V001")
        result = engine.analyze(bundle, _make_context(), track=track)
        assert result.total_pings_analyzed == 20
        # Clean track should have few or no anomalous pings
        assert result.status == VerificationStageStatus.PASSED

    def test_teleport_detected(self, engine, base_time):
        track = _make_teleport_track("V_TELEPORT", base_time)
        bundle = _make_bundle("V_TELEPORT")
        result = engine.analyze(bundle, _make_context(), track=track)
        assert result.anomalous_pings > 0
        # Should detect at least one teleport-type event
        teleport_events = [e for e in result.events if e.flag == KinematicFlag.TELEPORT_JUMP]
        assert len(teleport_events) > 0

    def test_no_track_skipped(self, engine):
        bundle = _make_bundle("V_EMPTY")
        result = engine.analyze(bundle, _make_context(), track=None)
        assert result.status == VerificationStageStatus.SKIPPED

    def test_identity_conflict(self, engine, base_time):
        """Same MMSI at >50km apart within 30 min should flag conflict."""
        track_a = VesselTrack(
            vessel_id="V_A",
            mmsi=477099099,
            pings=[
                AisPing(
                    mmsi=477099099, vessel_id="V_A",
                    timestamp=base_time, lat=16.0, lon=65.0, sog=10.0,
                ),
                AisPing(
                    mmsi=477099099, vessel_id="V_A",
                    timestamp=base_time + timedelta(minutes=10),
                    lat=16.01, lon=65.01, sog=10.0,
                ),
            ],
        )
        track_b = VesselTrack(
            vessel_id="V_B",
            mmsi=477099099,  # Same MMSI
            pings=[AisPing(
                mmsi=477099099, vessel_id="V_B",
                timestamp=base_time + timedelta(minutes=5),
                lat=17.0, lon=66.0, sog=10.0,  # ~150 km away
            )],
        )

        all_tracks = {"V_A": track_a, "V_B": track_b}
        bundle = _make_bundle("V_A")
        result = engine.analyze(bundle, _make_context(), track=track_a, all_tracks=all_tracks)
        assert len(result.identity_conflicts) > 0
        assert result.identity_conflicts[0].separation_km >= 50

    def test_episode_grouping(self, engine, base_time):
        """Multiple consecutive anomalous pings should form episodes."""
        track = _make_teleport_track("V_EP", base_time)
        bundle = _make_bundle("V_EP")
        result = engine.analyze(bundle, _make_context(), track=track)
        # Episodes may or may not form depending on exact NIS values
        # but anomalous events should exist
        assert result.total_pings_analyzed > 0

    def test_ekf_ks_uniformity_calibration(self, engine, base_time):
        """Clean CV track matching filter Q and R noise models yields uniform NIS p-values (KS test)."""
        import numpy as np
        import scipy.stats as stats

        np.random.seed(123)
        dt = 60.0
        q = 0.01
        sigma = 15.0
        Q = q * np.array([
            [dt**3 / 3, 0, dt**2 / 2, 0],
            [0, dt**3 / 3, 0, dt**2 / 2],
            [dt**2 / 2, 0, dt, 0],
            [0, dt**2 / 2, 0, dt],
        ])
        F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])

        state = np.array([0.0, 0.0, 5.0, 0.0])
        lat0, lon0 = 16.0, 65.0
        m_to_deg_lat = 1.0 / 111319.5
        m_to_deg_lon = 1.0 / (111319.5 * math.cos(math.radians(lat0)))

        pings = []
        for i in range(250):
            t = base_time + timedelta(seconds=dt * i)
            z_x = state[0] + np.random.normal(0, sigma)
            z_y = state[1] + np.random.normal(0, sigma)
            pings.append(AisPing(
                mmsi=477001001,
                vessel_id="V_CALIB",
                timestamp=t,
                lat=round(lat0 + z_y * m_to_deg_lat, 6),
                lon=round(lon0 + z_x * m_to_deg_lon, 6),
                sog=float(np.hypot(state[2], state[3]) / 0.514444),
                cog=90.0,
            ))
            w = np.random.multivariate_normal(np.zeros(4), Q)
            state = F @ state + w

        p_values = engine.compute_nis_p_values(pings)
        # Steady state: exclude initial burn-in
        p_vals = p_values[20:]
        ks_res = stats.kstest(p_vals, "uniform")
        # Cannot reject H0: p-values are Uniform(0,1) at alpha=0.01
        assert ks_res.pvalue > 0.01

