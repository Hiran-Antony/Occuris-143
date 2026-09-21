"""
Module 5 — Maritime Memory & Virtual Gateways — Maritime Memory & Journeys (§4.5)
Constructs the core unit of forensic memory: vessel_journeys.
Aggregates geodesic distances via pyproj.Geod, actual passage durations, speed profiles,
and tracks journey status (COMPLETED, IN_REGION, PARTIAL_ENTRY_ONLY, PARTIAL_EXIT_ONLY).
"""

from __future__ import annotations

import math
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pyproj import Geod

from src.ais.schemas import (
    EventType,
    ExpectedTimeBasis,
    GatewayCrossingEvent,
    JourneyStatus,
    VesselJourney,
    VesselTrack,
)

WGS84_GEOD = Geod(ellps="WGS84")


class MaritimeMemory:
    """Reconstructs and manages immutable vessel journey records."""

    def build_journeys(
        self,
        tracks: Dict[str, VesselTrack],
        crossing_events: List[GatewayCrossingEvent],
    ) -> Dict[str, VesselJourney]:
        """
        Synthesize vessel journeys by correlating AIS track trajectories
        with detected gateway crossings.
        """
        # Group crossings by vessel
        crossings_by_vessel: Dict[str, List[GatewayCrossingEvent]] = {}
        for ev in crossing_events:
            crossings_by_vessel.setdefault(ev.vessel_id, []).append(ev)

        journeys: Dict[str, VesselJourney] = {}

        for vessel_id, track in tracks.items():
            pings = track.pings
            if not pings:
                continue

            v_crossings = crossings_by_vessel.get(vessel_id, [])
            v_crossings.sort(key=lambda x: x.timestamp)

            # Compute total distance along WGS84 geodesic segments
            total_dist_km = 0.0
            speeds = []
            courses = []

            for i in range(len(pings) - 1):
                p1, p2 = pings[i], pings[i + 1]
                _, _, dist_m = WGS84_GEOD.inv(p1.lon, p1.lat, p2.lon, p2.lat)
                total_dist_km += dist_m / 1000.0
                speeds.append(p1.sog)
                courses.append(round(p1.cog / 10.0) * 10)  # bin into 10 deg bins

            if pings:
                speeds.append(pings[-1].sog)

            max_speed = round(max(speeds), 1) if speeds else 0.0

            # Calculate dominant course
            dominant_course = 0.0
            if courses:
                c_counts = Counter(courses)
                dominant_course = float(c_counts.most_common(1)[0][0])

            # Classify Entry and Exit
            entry_ev = next((c for c in v_crossings if c.event_type == EventType.ENTRY), None)
            exit_ev = next((c for c in v_crossings if c.event_type == EventType.EXIT), None)

            # Journey status logic (5 unambiguous states)
            if entry_ev and exit_ev:
                status = JourneyStatus.COMPLETED
                entry_gw = entry_ev.gateway_id
                entry_time = entry_ev.timestamp
                exit_gw = exit_ev.gateway_id
                exit_time = exit_ev.timestamp
            elif entry_ev and not exit_ev:
                status = JourneyStatus.IN_REGION
                entry_gw = entry_ev.gateway_id
                entry_time = entry_ev.timestamp
                exit_gw = None
                exit_time = pings[-1].timestamp
            elif not entry_ev and exit_ev:
                status = JourneyStatus.EXIT_ONLY_PARTIAL
                entry_gw = None
                entry_time = pings[0].timestamp
                exit_gw = exit_ev.gateway_id
                exit_time = exit_ev.timestamp
            else:
                # No crossings detected; all pings within observation window
                status = JourneyStatus.WINDOW_INTERIOR
                entry_gw = None
                entry_time = pings[0].timestamp
                exit_gw = None
                exit_time = pings[-1].timestamp

            # Actual passage duration in hours
            actual_duration_h = (pings[-1].timestamp - pings[0].timestamp).total_seconds() / 3600.0
            actual_duration_h = round(max(0.01, actual_duration_h), 2)

            # Average speed in knots (1 km = 0.539957 NM)
            avg_speed_kn = (
                round((total_dist_km * 0.539957) / actual_duration_h, 1)
                if actual_duration_h > 0.05
                else round(sum(speeds) / len(speeds), 1) if speeds else 0.0
            )

            journey = VesselJourney(
                journey_id=f"JRN_{vessel_id}_{pings[0].timestamp.strftime('%Y%m%d%H%M')}",
                vessel_id=vessel_id,
                vessel_name=track.vessel_name,
                entry_gateway=entry_gw,
                entry_time=entry_time,
                exit_gateway=exit_gw,
                exit_time=exit_time,
                distance_km=round(total_dist_km, 2),
                actual_duration_h=actual_duration_h,
                average_speed_kn=avg_speed_kn,
                max_observed_speed_kn=max_speed,
                dominant_course_deg=dominant_course,
                expected_basis=ExpectedTimeBasis.INSUFFICIENT_HISTORY,
                status=status,
            )

            journeys[vessel_id] = journey

        return journeys
