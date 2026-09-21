"""
Module 5 — Maritime Memory & Virtual Gateways — Innovation Layer B: Collective Anomaly Detection (§4.9)
Detects coordinated multi-vessel maritime anomalies using spatial-temporal fleet analytics:
- Rule R1 COORDINATED_DARK: >= 2 vessels with AIS gaps overlapping >= 10 min while last-known positions within 5 NM.
- Rule R2 RENDEZVOUS: pairwise distance < 500 m AND both SOG < 3 kn AND duration >= 20 min.
- Rule R3 CONVERGENCE: courses converge then parallel transit >= 30 min.
Evidence only — strictly zero guilt language.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

from src.ais.schemas import (
    CollectiveAnomalyEvent,
    CollectiveAnomalyType,
    VesselTrack,
)
from src.ais.track_builder import WGS84_GEOD, geodesic_distance_nm


class CollectiveAnomalyDetector:
    """Evaluates fleet-wide spatial-temporal relationships to flag multi-vessel anomalies."""

    def __init__(
        self,
        coordinated_dark_overlap_min: float = 10.0,
        coordinated_dark_nm: float = 5.0,
        rendezvous_dist_m: float = 500.0,
        rendezvous_sog_max: float = 3.0,
        rendezvous_min_duration_min: float = 20.0,
        dark_overlap_minutes: Optional[float] = None,
        dark_proximity_nm: Optional[float] = None,
        rendezvous_distance_m: Optional[float] = None,
        rendezvous_max_sog_kn: Optional[float] = None,
    ):
        self.dark_overlap_min = dark_overlap_minutes if dark_overlap_minutes is not None else coordinated_dark_overlap_min
        self.dark_dist_nm = dark_proximity_nm if dark_proximity_nm is not None else coordinated_dark_nm
        self.rendezvous_dist_m = rendezvous_distance_m if rendezvous_distance_m is not None else rendezvous_dist_m
        self.rendezvous_sog_max = rendezvous_max_sog_kn if rendezvous_max_sog_kn is not None else rendezvous_sog_max
        self.rendezvous_min_duration = rendezvous_min_duration_min

    def detect_anomalies(self, tracks: Dict[str, VesselTrack]) -> List[CollectiveAnomalyEvent]:
        """Run all collective anomaly rules across all pairwise vessel track combinations."""
        events: List[CollectiveAnomalyEvent] = []
        vessel_ids = sorted(tracks.keys())

        # 1. Rule R1: Coordinated Dark Vessels
        events.extend(self._detect_coordinated_dark(tracks, vessel_ids))

        # 2. Rule R2: Rendezvous at Sea
        events.extend(self._detect_rendezvous(tracks, vessel_ids))

        # 3. Rule R3: Trajectory Convergence & Parallel Transit
        events.extend(self._detect_convergence(tracks, vessel_ids))

        return events

    # Backwards compatibility alias
    detect_collective_anomalies = detect_anomalies

    def _detect_coordinated_dark(
        self,
        tracks: Dict[str, VesselTrack],
        vessel_ids: List[str],
    ) -> List[CollectiveAnomalyEvent]:
        """Detect pairwise AIS blackouts that overlap in time and occur within 5 NM."""
        events = []

        for v1_id, v2_id in combinations(vessel_ids, 2):
            t1, t2 = tracks[v1_id], tracks[v2_id]
            for g1 in t1.gaps:
                for g2 in t2.gaps:
                    # Calculate temporal overlap
                    start = max(g1.gap_start, g2.gap_start)
                    end = min(g1.gap_end, g2.gap_end)
                    overlap_sec = (end - start).total_seconds()
                    overlap_min = overlap_sec / 60.0

                    if overlap_min >= self.dark_overlap_min:
                        # Geodesic distance between last-known positions before blackout
                        dist_nm = geodesic_distance_nm(g1.start_lat, g1.start_lon, g2.start_lat, g2.start_lon)

                        if dist_nm <= self.dark_dist_nm:
                            events.append(
                                CollectiveAnomalyEvent(
                                    event_id=f"ANOM_DARK_{hashlib.sha256(f'{v1_id}_{v2_id}_{start.isoformat()}'.encode()).hexdigest()[:8].upper()}",
                                    vessel_cluster=[v1_id, v2_id],
                                    anomaly_type=CollectiveAnomalyType.COORDINATED_DARK,
                                    window_start=start,
                                    window_end=end,
                                    evidence={
                                        "rule": "R1_COORDINATED_DARK",
                                        "temporal_overlap_minutes": round(overlap_min, 1),
                                        "separation_distance_nm": round(dist_nm, 2),
                                        "threshold_overlap_min": self.dark_overlap_min,
                                        "threshold_separation_nm": self.dark_dist_nm,
                                        "v1_gap": [g1.gap_start.isoformat(), g1.gap_end.isoformat()],
                                        "v2_gap": [g2.gap_start.isoformat(), g2.gap_end.isoformat()],
                                    },
                                )
                            )

        return events

    def _detect_rendezvous(
        self,
        tracks: Dict[str, VesselTrack],
        vessel_ids: List[str],
    ) -> List[CollectiveAnomalyEvent]:
        """
        Detect slow-speed close proximity meetings (< 500m separation, SOG < 3.0 kn, >= 20 min).
        """
        events = []

        for v1_id, v2_id in combinations(vessel_ids, 2):
            pings1 = tracks[v1_id].pings
            pings2 = tracks[v2_id].pings
            if not pings1 or not pings2:
                continue

            # Find overlapping time intervals
            close_intervals: List[Tuple[datetime, datetime, float]] = []
            current_start = None
            last_time = None
            min_dist_observed = 999999.0

            # Step through pings from v1 and find interpolated/closest ping in v2
            i2 = 0
            for p1 in pings1:
                while i2 < len(pings2) - 1 and pings2[i2 + 1].timestamp <= p1.timestamp:
                    i2 += 1

                p2 = pings2[i2]
                time_diff = abs((p1.timestamp - p2.timestamp).total_seconds())
                if time_diff > 300.0:  # Within 5 minutes
                    continue

                _, _, dist_m = WGS84_GEOD.inv(p1.lon, p1.lat, p2.lon, p2.lat)

                if dist_m < self.rendezvous_dist_m and p1.sog < self.rendezvous_sog_max and p2.sog < self.rendezvous_sog_max:
                    if current_start is None:
                        current_start = p1.timestamp
                    last_time = p1.timestamp
                    min_dist_observed = min(min_dist_observed, dist_m)
                else:
                    if current_start and last_time:
                        dur_min = (last_time - current_start).total_seconds() / 60.0
                        if dur_min >= self.rendezvous_min_duration:
                            close_intervals.append((current_start, last_time, min_dist_observed))
                        current_start = None
                        min_dist_observed = 999999.0

            if current_start and last_time:
                dur_min = (last_time - current_start).total_seconds() / 60.0
                if dur_min >= self.rendezvous_min_duration:
                    close_intervals.append((current_start, last_time, min_dist_observed))

            for start, end, min_d in close_intervals:
                events.append(
                    CollectiveAnomalyEvent(
                        event_id=f"ANOM_RDVZ_{hashlib.sha256(f'{v1_id}_{v2_id}_{start.isoformat()}'.encode()).hexdigest()[:8].upper()}",
                        vessel_cluster=[v1_id, v2_id],
                        anomaly_type=CollectiveAnomalyType.RENDEZVOUS,
                        window_start=start,
                        window_end=end,
                        evidence={
                            "rule": "R2_RENDEZVOUS",
                            "duration_minutes": round((end - start).total_seconds() / 60.0, 1),
                            "minimum_separation_m": round(min_d, 1),
                            "threshold_separation_m": self.rendezvous_dist_m,
                            "threshold_sog_kn": self.rendezvous_sog_max,
                            "note": "Pairwise loitering within 500m proximity",
                        },
                    )
                )

        return events

    def _detect_convergence(
        self,
        tracks: Dict[str, VesselTrack],
        vessel_ids: List[str],
    ) -> List[CollectiveAnomalyEvent]:
        """Detect vessels whose courses converge and proceed in parallel for >= 30 min."""
        events = []

        for v1_id, v2_id in combinations(vessel_ids, 2):
            pings1 = tracks[v1_id].pings
            pings2 = tracks[v2_id].pings
            if len(pings1) < 10 or len(pings2) < 10:
                continue

            # Compare heading alignment and separation
            parallel_start = None
            parallel_end = None
            i2 = 0

            for p1 in pings1:
                while i2 < len(pings2) - 1 and pings2[i2 + 1].timestamp <= p1.timestamp:
                    i2 += 1
                p2 = pings2[i2]

                if abs((p1.timestamp - p2.timestamp).total_seconds()) > 300.0:
                    continue

                _, _, dist_m = WGS84_GEOD.inv(p1.lon, p1.lat, p2.lon, p2.lat)
                heading_diff = abs((p1.cog - p2.cog + 180.0) % 360.0 - 180.0)

                # Parallel if headings within 15 deg and separation between 500m and 3000m
                if heading_diff < 15.0 and 500.0 <= dist_m <= 3000.0:
                    if parallel_start is None:
                        parallel_start = p1.timestamp
                    parallel_end = p1.timestamp
                else:
                    if parallel_start and parallel_end:
                        dur_min = (parallel_end - parallel_start).total_seconds() / 60.0
                        if dur_min >= 30.0:
                            events.append(
                                CollectiveAnomalyEvent(
                                    event_id=f"ANOM_CONV_{hashlib.sha256(f'{v1_id}_{v2_id}_{parallel_start.isoformat()}'.encode()).hexdigest()[:8].upper()}",
                                    vessel_cluster=[v1_id, v2_id],
                                    anomaly_type=CollectiveAnomalyType.CONVERGENCE,
                                    window_start=parallel_start,
                                    window_end=parallel_end,
                                    evidence={
                                        "rule": "R3_CONVERGENCE",
                                        "parallel_duration_minutes": round(dur_min, 1),
                                        "heading_alignment_deg": round(heading_diff, 1),
                                        "mean_separation_m": round(dist_m, 1),
                                    },
                                )
                            )
                        parallel_start = None

        return events
