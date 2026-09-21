"""
Module 6 — Stage 3: Kinematic Consistency Engine
Constant-velocity Extended Kalman Filter in local ENU frame.
Per-ping NIS → chi²(2) p-value; EPISODE = ≥ episode_min_pings consecutive p < chi2_alpha
OR single p < extreme_p. Types each episode via innovation direction + implied kinematics.
Detects IDENTITY_CONFLICT when same MMSI appears > min_sep_km apart within max_dt_min.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pyproj import Geod
from scipy import stats as scipy_stats

from src.ais.schemas import (
    AisPing,
    CaseContextV1,
    EvidenceBundleV1,
    IdentityConflict,
    KinematicEpisode,
    KinematicEvent,
    KinematicFlag,
    KinematicReport,
    VesselTrack,
    VerificationStageStatus,
)
from src.ais.track_builder import geodesic_distance_km

WGS84 = Geod(ellps="WGS84")
METERS_PER_DEG_LAT = 111_320.0  # Average metres per degree latitude


def _lla_to_enu(lat: float, lon: float, ref_lat: float, ref_lon: float) -> Tuple[float, float]:
    """Convert WGS84 (lat, lon) to local East-North-Up (x_east, y_north) in metres."""
    d_lat = lat - ref_lat
    d_lon = lon - ref_lon
    y_north = d_lat * METERS_PER_DEG_LAT
    x_east = d_lon * METERS_PER_DEG_LAT * math.cos(math.radians(ref_lat))
    return x_east, y_north


class KinematicEngine:
    """Stage 3: Constant-velocity EKF for kinematic consistency checking."""

    def __init__(self, config: Dict[str, Any]):
        ekf_cfg = config.get("ekf", {})
        self.dt_s = float(ekf_cfg.get("dt_s", 600))
        self.process_noise_q = float(ekf_cfg.get("process_noise_q", 0.01))
        self.measurement_sigma_m = float(ekf_cfg.get("measurement_sigma_m", 15.0))
        self.chi2_alpha = float(ekf_cfg.get("chi2_alpha", 0.01))
        self.episode_min_pings = int(ekf_cfg.get("episode_min_pings", 3))
        self.extreme_p = float(ekf_cfg.get("extreme_p", 1e-6))

        # Identity conflict config
        id_cfg = config.get("identity_conflict", {})
        self.min_sep_km = float(id_cfg.get("min_sep_km", 50))
        self.max_dt_min = float(id_cfg.get("max_dt_min", 30))

        # Vessel class max speeds from region config
        region_cfg = config.get("_region", {})
        self.vessel_max_speeds = region_cfg.get("vessel_class_max_speeds_kn", {"default": 18.0})

    def analyze(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
        track: Optional[VesselTrack] = None,
        all_tracks: Optional[Dict[str, VesselTrack]] = None,
    ) -> KinematicReport:
        """Run EKF analysis on the vessel track."""
        if track is None or len(track.pings) < 2:
            return KinematicReport(
                vessel_id=bundle.vessel_id,
                total_pings_analyzed=0,
                anomalous_pings=0,
                status=VerificationStageStatus.SKIPPED,
            )

        pings = track.pings
        events = self._run_ekf(pings, bundle.vessel_id)
        episodes = self._build_episodes(events, bundle.vessel_id)

        # Identity conflict detection
        conflicts: List[IdentityConflict] = []
        if all_tracks:
            conflicts = self._detect_identity_conflicts(track, all_tracks)

        anomalous_count = len(events)
        status = VerificationStageStatus.PASSED
        if episodes or conflicts:
            status = VerificationStageStatus.FLAGGED

        return KinematicReport(
            vessel_id=bundle.vessel_id,
            total_pings_analyzed=len(pings),
            anomalous_pings=anomalous_count,
            episodes=episodes,
            identity_conflicts=conflicts,
            events=events,
            status=status,
        )

    def compute_nis_p_values(self, pings: List[AisPing]) -> List[float]:
        """Compute NIS p-values for all pings in a track (used for EKF calibration guard)."""
        if len(pings) < 2:
            return []

        ref_lat = pings[0].lat
        ref_lon = pings[0].lon

        x0, y0 = _lla_to_enu(pings[0].lat, pings[0].lon, ref_lat, ref_lon)
        x1, y1 = _lla_to_enu(pings[1].lat, pings[1].lon, ref_lat, ref_lon)
        dt0 = max(1.0, (pings[1].timestamp - pings[0].timestamp).total_seconds())
        vx0 = (x1 - x0) / dt0
        vy0 = (y1 - y0) / dt0

        state = np.array([x0, y0, vx0, vy0], dtype=np.float64)
        P = np.diag([self.measurement_sigma_m**2, self.measurement_sigma_m**2, 10.0**2, 10.0**2])
        H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float64)
        R = np.eye(2) * self.measurement_sigma_m**2

        p_values: List[float] = []

        for i in range(1, len(pings)):
            dt = max(1.0, (pings[i].timestamp - pings[i - 1].timestamp).total_seconds())
            F = np.array([
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ], dtype=np.float64)

            q = self.process_noise_q
            Q = q * np.array([
                [dt**3/3, 0, dt**2/2, 0],
                [0, dt**3/3, 0, dt**2/2],
                [dt**2/2, 0, dt, 0],
                [0, dt**2/2, 0, dt],
            ], dtype=np.float64)

            state_pred = F @ state
            P_pred = F @ P @ F.T + Q

            x_meas, y_meas = _lla_to_enu(pings[i].lat, pings[i].lon, ref_lat, ref_lon)
            z = np.array([x_meas, y_meas])
            innovation = z - H @ state_pred
            S = H @ P_pred @ H.T + R

            try:
                S_inv = np.linalg.inv(S)
                nis = float(innovation.T @ S_inv @ innovation)
            except np.linalg.LinAlgError:
                nis = 999.0

            p_val = float(1.0 - scipy_stats.chi2.cdf(nis, df=2))
            p_values.append(p_val)

            K = P_pred @ H.T @ S_inv if nis < 999.0 else np.zeros((4, 2))
            state = state_pred + K @ innovation
            P = (np.eye(4) - K @ H) @ P_pred

        return p_values

    def _run_ekf(self, pings: List[AisPing], vessel_id: str) -> List[KinematicEvent]:
        """Run constant-velocity EKF and detect anomalous pings."""
        if len(pings) < 2:
            return []

        ref_lat = pings[0].lat
        ref_lon = pings[0].lon

        # Initial state: [x, y, vx, vy] in ENU
        x0, y0 = _lla_to_enu(pings[0].lat, pings[0].lon, ref_lat, ref_lon)

        # Estimate initial velocity from first two pings
        x1, y1 = _lla_to_enu(pings[1].lat, pings[1].lon, ref_lat, ref_lon)
        dt0 = max(1.0, (pings[1].timestamp - pings[0].timestamp).total_seconds())
        vx0 = (x1 - x0) / dt0
        vy0 = (y1 - y0) / dt0

        state = np.array([x0, y0, vx0, vy0], dtype=np.float64)
        # State covariance
        P = np.diag([self.measurement_sigma_m**2, self.measurement_sigma_m**2,
                      10.0**2, 10.0**2])

        # Measurement matrix (observe position only)
        H = np.array([[1, 0, 0, 0],
                       [0, 1, 0, 0]], dtype=np.float64)

        # Measurement noise
        R = np.eye(2) * self.measurement_sigma_m**2

        events: List[KinematicEvent] = []
        max_speed_kn = float(self.vessel_max_speeds.get("default", 18.0))
        max_speed_ms = max_speed_kn * 0.514444  # knots to m/s

        for i in range(1, len(pings)):
            dt = max(1.0, (pings[i].timestamp - pings[i - 1].timestamp).total_seconds())

            # State transition matrix (constant velocity)
            F = np.array([
                [1, 0, dt, 0],
                [0, 1, 0, dt],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ], dtype=np.float64)

            # Process noise matrix
            q = self.process_noise_q
            Q = q * np.array([
                [dt**3/3, 0, dt**2/2, 0],
                [0, dt**3/3, 0, dt**2/2],
                [dt**2/2, 0, dt, 0],
                [0, dt**2/2, 0, dt],
            ], dtype=np.float64)

            # Predict
            state_pred = F @ state
            P_pred = F @ P @ F.T + Q

            # Measurement
            x_meas, y_meas = _lla_to_enu(pings[i].lat, pings[i].lon, ref_lat, ref_lon)
            z = np.array([x_meas, y_meas])

            # Innovation
            innovation = z - H @ state_pred
            S = H @ P_pred @ H.T + R

            # Normalised Innovation Squared (NIS) — chi²(2)
            try:
                S_inv = np.linalg.inv(S)
                nis = float(innovation.T @ S_inv @ innovation)
            except np.linalg.LinAlgError:
                nis = 999.0

            p_value = float(1.0 - scipy_stats.chi2.cdf(nis, df=2))

            # Kalman gain and update
            K = P_pred @ H.T @ S_inv if nis < 999.0 else np.zeros((4, 2))
            state = state_pred + K @ innovation
            P = (np.eye(4) - K @ H) @ P_pred

            # Check anomaly
            is_anomalous = p_value < self.chi2_alpha
            is_extreme = p_value < self.extreme_p

            if is_anomalous or is_extreme:
                # Classify the kinematic flag
                implied_speed_ms = math.hypot(innovation[0], innovation[1]) / dt
                implied_speed_kn = implied_speed_ms / 0.514444

                # Course change from innovation direction
                prev_course = math.atan2(state_pred[2], state_pred[3])
                innov_course = math.atan2(innovation[0], innovation[1])
                course_change = abs(math.degrees(innov_course - prev_course))
                if course_change > 180:
                    course_change = 360 - course_change

                flag = self._classify_flag(implied_speed_kn, course_change, max_speed_kn, nis)

                events.append(KinematicEvent(
                    vessel_id=vessel_id,
                    ping_index=i,
                    timestamp=pings[i].timestamp,
                    lat=pings[i].lat,
                    lon=pings[i].lon,
                    nis_value=round(nis, 4),
                    p_value=p_value,
                    flag=flag,
                    implied_speed_kn=round(implied_speed_kn, 2),
                    implied_course_change_deg=round(course_change, 2),
                    detail=f"NIS={nis:.2f}, p={p_value:.2e}, implied_speed={implied_speed_kn:.1f}kn",
                ))

        return events

    def _classify_flag(
        self, implied_speed_kn: float, course_change: float,
        max_speed_kn: float, nis: float
    ) -> KinematicFlag:
        """Classify the kinematic anomaly type from innovation characteristics."""
        if implied_speed_kn > max_speed_kn * 3:
            return KinematicFlag.TELEPORT_JUMP
        elif implied_speed_kn > max_speed_kn * 1.2:
            return KinematicFlag.SPEED_IMPOSSIBLE
        elif course_change > 90:
            return KinematicFlag.COURSE_DISCONTINUITY
        else:
            return KinematicFlag.TURN_RATE_OUTLIER

    def _build_episodes(
        self, events: List[KinematicEvent], vessel_id: str
    ) -> List[KinematicEpisode]:
        """Group consecutive anomalous events into episodes."""
        if not events:
            return []

        episodes: List[KinematicEpisode] = []
        current_run: List[KinematicEvent] = [events[0]]

        for i in range(1, len(events)):
            if events[i].ping_index == events[i - 1].ping_index + 1:
                current_run.append(events[i])
            else:
                if len(current_run) >= self.episode_min_pings:
                    episodes.append(self._make_episode(current_run, vessel_id))
                elif any(e.p_value < self.extreme_p for e in current_run):
                    episodes.append(self._make_episode(current_run, vessel_id))
                current_run = [events[i]]

        # Final run
        if len(current_run) >= self.episode_min_pings:
            episodes.append(self._make_episode(current_run, vessel_id))
        elif any(e.p_value < self.extreme_p for e in current_run):
            episodes.append(self._make_episode(current_run, vessel_id))

        return episodes

    def _make_episode(
        self, events: List[KinematicEvent], vessel_id: str
    ) -> KinematicEpisode:
        """Create a KinematicEpisode from a run of events."""
        # Determine dominant flag type
        flag_counts: Dict[KinematicFlag, int] = {}
        for e in events:
            flag_counts[e.flag] = flag_counts.get(e.flag, 0) + 1
        dominant_flag = max(flag_counts, key=flag_counts.get)  # type: ignore

        duration = 0.0
        if len(events) >= 2:
            duration = (events[-1].timestamp - events[0].timestamp).total_seconds() / 60.0

        return KinematicEpisode(
            vessel_id=vessel_id,
            events=events,
            episode_type=dominant_flag,
            start_index=events[0].ping_index,
            end_index=events[-1].ping_index,
            duration_minutes=round(duration, 2),
        )

    def _detect_identity_conflicts(
        self, track: VesselTrack, all_tracks: Dict[str, VesselTrack]
    ) -> List[IdentityConflict]:
        """Detect same MMSI appearing at impossibly separated locations."""
        from datetime import timedelta

        conflicts: List[IdentityConflict] = []
        max_dt = timedelta(minutes=self.max_dt_min)

        for other_id, other_track in all_tracks.items():
            if other_id == track.vessel_id:
                continue
            if other_track.mmsi != track.mmsi or track.mmsi == 0:
                continue

            # Check pairwise temporal proximity
            for p1 in track.pings:
                for p2 in other_track.pings:
                    dt = abs((p1.timestamp - p2.timestamp).total_seconds())
                    if dt <= max_dt.total_seconds():
                        sep_km = geodesic_distance_km(p1.lat, p1.lon, p2.lat, p2.lon)
                        if sep_km >= self.min_sep_km:
                            conflicts.append(IdentityConflict(
                                vessel_id=track.vessel_id,
                                mmsi=track.mmsi,
                                position_a={"lat": p1.lat, "lon": p1.lon,
                                             "timestamp": p1.timestamp.isoformat()},
                                position_b={"lat": p2.lat, "lon": p2.lon,
                                             "timestamp": p2.timestamp.isoformat()},
                                separation_km=round(sep_km, 2),
                                dt_minutes=round(dt / 60.0, 2),
                            ))
                            return conflicts  # One conflict is sufficient evidence

        return conflicts
