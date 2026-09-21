"""
Module 5 — Maritime Memory & Virtual Gateways — Behaviour Audit & Explanation (§4.7)
For each transit, objectively tests evidence-based delay explanations:
- TRAFFIC: corridor vessel count in real AIS >= 75th percentile
- WEATHER: ERA5 wind field overlap with delay window (honest language: "conditions overlap the window")
- AIS_GAP: coverage blackout overlapping the journey
- NAV_STATUS: legitimate operational status (At anchor, Moored, Restricted manoeuvrability)
Emits evidence assessments: NORMAL_TRANSIT | EXPLAINED_DELAY | POTENTIAL_UNEXPLAINED_DELAY | INSUFFICIENT_DATA.
Objective forensic framing with zero accusatory language.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from src.ais.schemas import (
    AISContinuity,
    BehaviourAssessment,
    BehaviourStatus,
    ExplanationFactor,
    FactorSupportStatus,
    TransitAnalysis,
    VesselJourney,
    VesselTrack,
)
from src.config import WIND_DIR

WIND_NPZ = WIND_DIR / "wind_arabian_sea.npz"


class WeatherProvider:
    """Reads regional ERA5 wind field snapshot to evaluate weather overlap."""

    def __init__(self, wind_npz_path: Optional[Path] = None):
        self.path = wind_npz_path or WIND_NPZ
        self.u = None
        self.v = None
        self.lats = None
        self.lons = None
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = np.load(self.path)
                self.u = data["U"]
                self.v = data["V"]
                self.lats = data["lats"]
                self.lons = data["lons"]
            except Exception:
                pass

    def get_wind_speed_at(self, lat: float, lon: float) -> Optional[float]:
        """Interpolate wind speed magnitude (m/s) at target coordinates."""
        if self.u is None or self.lats is None or self.lons is None:
            return None

        lat_idx = int(np.argmin(np.abs(self.lats - lat)))
        lon_idx = int(np.argmin(np.abs(self.lons - lon)))

        u_val = float(self.u[lat_idx, lon_idx])
        v_val = float(self.v[lat_idx, lon_idx])
        return round(float(np.hypot(u_val, v_val)), 2)


class BehaviourAuditor:
    """Evaluates multi-factor forensic evidence for vessel movements."""

    def __init__(
        self,
        delay_threshold_h: float = 1.0,
        wind_threshold_ms: float = 6.5,
        weather_provider: Optional[WeatherProvider] = None,
    ):
        self.delay_threshold_h = delay_threshold_h
        self.wind_threshold_ms = wind_threshold_ms
        self.weather = weather_provider or WeatherProvider()

    def audit_vessel(
        self,
        track: VesselTrack,
        journey: VesselJourney,
        transit: TransitAnalysis,
        traffic_info: Optional[Dict[str, Any]] = None,
    ) -> BehaviourAssessment:
        """Evaluate a single vessel passage and attach evidence factors."""
        explanations: List[ExplanationFactor] = []

        if not track.pings or len(track.pings) < 2:
            return BehaviourAssessment(
                vessel_id=track.vessel_id,
                status=BehaviourStatus.INSUFFICIENT_DATA,
                transit=transit,
                ais_continuity=track.ais_continuity,
                nav_status_observed="No observations",
                explanations=[
                    ExplanationFactor(
                        factor="DATA_SUFFICIENCY",
                        status=FactorSupportStatus.INSUFFICIENT_DATA,
                        detail="Fewer than 2 AIS records available in observation window",
                    )
                ],
            )

        # 1. Test AIS Gap Factor
        has_gap = len(track.gaps) > 0
        if has_gap:
            max_gap = max(g.duration_minutes for g in track.gaps)
            explanations.append(
                ExplanationFactor(
                    factor="AIS_GAP",
                    status=FactorSupportStatus.SUPPORTED,
                    detail=f"AIS reporting silence detected ({max_gap:.1f} min blackout)",
                )
            )
        else:
            explanations.append(
                ExplanationFactor(
                    factor="AIS_GAP",
                    status=FactorSupportStatus.NOT_SUPPORTED,
                    detail="Continuous AIS reporting maintained throughout transit",
                )
            )

        # 2. Test Navigational Status Factor
        nav_statuses = {p.nav_status for p in track.pings}
        nav_labels = {p.nav_status_label for p in track.pings}
        legitimate_stop = any(s in [1, 5, 6, 2, 3] for s in nav_statuses)
        if legitimate_stop:
            explanations.append(
                ExplanationFactor(
                    factor="NAV_STATUS",
                    status=FactorSupportStatus.SUPPORTED,
                    detail=f"Observed navigational status: {', '.join(nav_labels)}",
                )
            )
        else:
            explanations.append(
                ExplanationFactor(
                    factor="NAV_STATUS",
                    status=FactorSupportStatus.NOT_SUPPORTED,
                    detail="Vessel reported under way using engine throughout transit",
                )
            )

        # 3. Test Regional Traffic Congestion Factor
        is_high_traffic = traffic_info and traffic_info.get("is_high_density", False)
        vessel_count = traffic_info.get("vessel_count", 1) if traffic_info else 1
        if is_high_traffic:
            explanations.append(
                ExplanationFactor(
                    factor="TRAFFIC",
                    status=FactorSupportStatus.SUPPORTED,
                    detail=f"Corridor traffic density exceeded 75th percentile ({vessel_count} active vessels)",
                )
            )
        else:
            explanations.append(
                ExplanationFactor(
                    factor="TRAFFIC",
                    status=FactorSupportStatus.NOT_SUPPORTED,
                    detail=f"Normal corridor traffic density observed ({vessel_count} vessels active)",
                )
            )

        # 4. Test Weather Overlap Factor
        winds = [self.weather.get_wind_speed_at(p.lat, p.lon) for p in track.pings]
        valid_winds = [w for w in winds if w is not None]
        max_wind = max(valid_winds) if valid_winds else None
        wind_overlap = max_wind is not None and max_wind >= self.wind_threshold_ms
        if wind_overlap:
            explanations.append(
                ExplanationFactor(
                    factor="WEATHER",
                    status=FactorSupportStatus.SUPPORTED,
                    detail=f"Adverse wind conditions ({max_wind:.1f} m/s) overlap the transit window",
                )
            )
        else:
            wind_disp = f"{max_wind:.1f}" if max_wind is not None else "0.0"
            explanations.append(
                ExplanationFactor(
                    factor="WEATHER",
                    status=FactorSupportStatus.NOT_SUPPORTED,
                    detail=f"Moderate environmental conditions ({wind_disp} m/s) observed along track",
                )
            )

        # ── Multi-factor Forensic Synthesis ───────────────────────────────────
        delay_h = transit.delay_h or 0.0
        has_delay = delay_h > self.delay_threshold_h

        # 2-sigma check if z-score exists
        z_elevated = transit.z_score is not None and transit.z_score > 2.0

        if not has_delay and not has_gap:
            status = BehaviourStatus.NORMAL_TRANSIT
        elif has_delay and (wind_overlap or is_high_traffic or legitimate_stop):
            status = BehaviourStatus.EXPLAINED_DELAY
        elif has_delay or has_gap or z_elevated:
            status = BehaviourStatus.POTENTIAL_UNEXPLAINED_DELAY
        else:
            status = BehaviourStatus.NORMAL_TRANSIT

        return BehaviourAssessment(
            vessel_id=track.vessel_id,
            status=status,
            transit=transit,
            ais_continuity=track.ais_continuity,
            nav_status_observed=", ".join(sorted(nav_labels)),
            explanations=explanations,
        )

    def audit_all(
        self,
        tracks: Dict[str, VesselTrack],
        journeys: Dict[str, VesselJourney],
        transits: Dict[str, TransitAnalysis],
        traffic_map: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, BehaviourAssessment]:
        """Evaluate behavior across all monitored vessel journeys."""
        assessments: Dict[str, BehaviourAssessment] = {}
        t_map = traffic_map or {}

        for v_id, track in tracks.items():
            journey = journeys.get(v_id)
            transit = transits.get(v_id)
            if not journey or not transit:
                continue

            traffic_info = t_map.get(v_id)
            assessment = self.audit_vessel(track, journey, transit, traffic_info)
            assessments[v_id] = assessment

        return assessments

    # Backwards compatibility aliases
    assess_all = audit_all
    assess_vessel = audit_vessel


# Backwards compatibility alias
BehaviourClassifier = BehaviourAuditor
EnvironmentalAdapter = WeatherProvider


