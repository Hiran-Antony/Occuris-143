"""
Module 5 — Maritime Memory & Virtual Gateways — Track Builder (§4.2)
Builds chronological vessel tracks, computes geodesic segment distances using pyproj.Geod,
determines implied segment velocities, and detects AIS coverage gaps as behavioral context.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pyproj import Geod

from src.ais.schemas import AisGap, AisPing, VesselTrack

# Standard WGS84 Geodesic Calculator
WGS84_GEOD = Geod(ellps="WGS84")
METERS_PER_NM = 1852.0


def geodesic_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate exact WGS84 geodesic distance in kilometres between two geographic points."""
    _, _, dist_m = WGS84_GEOD.inv(lon1, lat1, lon2, lat2)
    return dist_m / 1000.0


def geodesic_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate exact WGS84 geodesic distance in nautical miles between two geographic points."""
    _, _, dist_m = WGS84_GEOD.inv(lon1, lat1, lon2, lat2)
    return dist_m / METERS_PER_NM


class TrackBuilder:
    """Constructs continuous geodesic vessel trajectories and flags reporting blackouts."""

    def __init__(self, gap_threshold_min: float = 15.0, ais_gap_threshold_min: Optional[float] = None):
        self.gap_threshold_min = ais_gap_threshold_min if ais_gap_threshold_min is not None else gap_threshold_min

    def build_tracks(self, records: List[AisPing]) -> Dict[str, VesselTrack]:
        """
        Group records by vessel_id, sort chronologically, compute geodesic segment metrics,
        and identify reporting silence intervals exceeding the threshold.
        """
        grouped: Dict[str, List[AisPing]] = defaultdict(list)
        for r in records:
            grouped[r.vessel_id].append(r)

        tracks: Dict[str, VesselTrack] = {}
        for vessel_id, pings in grouped.items():
            pings.sort(key=lambda x: x.timestamp)
            vessel_name = pings[0].vessel_name if pings else ""
            mmsi = pings[0].mmsi if pings else 0

            gaps = self.detect_gaps(vessel_id, pings)
            total_dist_km = 0.0
            for i in range(len(pings) - 1):
                total_dist_km += geodesic_distance_km(pings[i].lat, pings[i].lon, pings[i + 1].lat, pings[i + 1].lon)

            tracks[vessel_id] = VesselTrack(
                vessel_id=vessel_id,
                vessel_name=vessel_name,
                mmsi=mmsi,
                pings=pings,
                gaps=gaps,
                total_distance_km=round(total_dist_km, 3),
            )

        return tracks

    def detect_gaps(self, vessel_id: str, pings: List[AisPing]) -> List[AisGap]:
        """
        Detect reporting intervals exceeding gap_threshold_min.
        Classified strictly as behavioral context, never as a definitive guilt verdict.
        """
        gaps: List[AisGap] = []
        if len(pings) < 2:
            return gaps

        for i in range(len(pings) - 1):
            p1 = pings[i]
            p2 = pings[i + 1]
            diff_sec = (p2.timestamp - p1.timestamp).total_seconds()
            diff_min = diff_sec / 60.0

            if diff_min >= self.gap_threshold_min:
                dist_nm = geodesic_distance_nm(p1.lat, p1.lon, p2.lat, p2.lon)
                duration_h = diff_sec / 3600.0
                implied_sog = round(dist_nm / duration_h, 2) if duration_h > 0 else 0.0

                gaps.append(
                    AisGap(
                        vessel_id=vessel_id,
                        gap_start=p1.timestamp,
                        gap_end=p2.timestamp,
                        duration_minutes=round(diff_min, 2),
                        start_lat=p1.lat,
                        start_lon=p1.lon,
                        end_lat=p2.lat,
                        end_lon=p2.lon,
                        implied_speed_knots=implied_sog,
                    )
                )

        return gaps

    @staticmethod
    def get_state_at_time(track: VesselTrack, target_time: datetime) -> Optional[Dict[str, Any]]:
        """Extract vessel state and trail at or immediately prior to a target UTC timestamp."""
        if not track.pings:
            return None

        # Normalize target_time to UTC
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)

        visible = [p for p in track.pings if p.timestamp <= target_time]
        if not visible:
            return None

        current = visible[-1]
        trail = [{"lat": p.lat, "lon": p.lon} for p in visible]

        return {
            "vessel_id": track.vessel_id,
            "vessel_name": track.vessel_name,
            "mmsi": track.mmsi,
            "lat": current.lat,
            "lon": current.lon,
            "sog": current.sog,
            "cog": current.cog,
            "nav_status": current.nav_status,
            "nav_status_label": current.nav_status_label,
            "timestamp": current.timestamp.isoformat(),
            "trail": trail,
        }
