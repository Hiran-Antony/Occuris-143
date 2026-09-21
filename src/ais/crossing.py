"""
Module 5 — Maritime Memory & Virtual Gateways — Crossing Detection Engine (§4.4)
Detects corridor boundary intersections, computes mathematically exact linear time interpolation:
t_cross = t1 + r * (t2 - t1), enforces a strict journey state machine (OUTSIDE -> ENTRY -> INSIDE -> EXIT -> OUTSIDE),
and suppresses duplicate events using composite idempotency keys.
"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple, Union

from shapely.geometry import LineString, Point, Polygon

from src.ais.gateways import GatewayManager, get_gateway_manager
from src.ais.schemas import EventType, GatewayCorridor, GatewayCrossingEvent, VesselTrack


class CrossingDetector:
    """
    Geospatial crossing engine detecting virtual corridor entry/exit milestones
    with sub-second interpolated crossing times.
    """

    def __init__(
        self,
        gateway_manager: Optional[GatewayManager] = None,
        min_duplicate_interval_sec: float = 300.0,
    ):
        self.gateway_mgr = gateway_manager or get_gateway_manager()
        self.min_duplicate_interval_sec = min_duplicate_interval_sec

    def detect_crossings(
        self,
        tracks: Union[Dict[str, VesselTrack], VesselTrack],
        gateways: Optional[List[GatewayCorridor]] = None,
    ) -> List[GatewayCrossingEvent]:
        """
        Evaluate all vessel trajectories against configured corridors.
        Returns chronologically sorted, deduplicated, state-validated crossing events.
        """
        gws = gateways or self.gateway_mgr.gateways
        if isinstance(tracks, VesselTrack):
            events = self.detect_track_crossings(tracks, gws)
            events.sort(key=lambda e: e.timestamp)
            return events

        events: List[GatewayCrossingEvent] = []
        for vessel_id, track in tracks.items():
            v_events = self.detect_track_crossings(track, gws)
            events.extend(v_events)

        events.sort(key=lambda e: e.timestamp)
        return events

    def detect_track_crossings(
        self,
        track: VesselTrack,
        gateways: List[GatewayCorridor],
    ) -> List[GatewayCrossingEvent]:
        """Detect crossing events for a single vessel trajectory using state machine tracking."""
        events: List[GatewayCrossingEvent] = []
        pings = track.pings
        if len(pings) < 2:
            return events

        # Per-gateway state machine tracking: 'OUTSIDE' | 'INSIDE'
        vessel_states: Dict[str, str] = {}
        seen_keys: Set[str] = set()

        # Initialize state based on first ping
        p0_pt = Point(pings[0].lon, pings[0].lat)
        for gw in gateways:
            geom = self.gateway_mgr.get_geometry(gw.gateway_id)
            if geom and geom.contains(p0_pt):
                vessel_states[gw.gateway_id] = "INSIDE"
            else:
                vessel_states[gw.gateway_id] = "OUTSIDE"

        for i in range(len(pings) - 1):
            p1 = pings[i]
            p2 = pings[i + 1]

            seg_line = LineString([(p1.lon, p1.lat), (p2.lon, p2.lat)])
            seg_len_deg = seg_line.length
            if seg_len_deg < 1e-9:
                continue

            for gw in gateways:
                corridor_poly = self.gateway_mgr.get_geometry(gw.gateway_id)
                if not corridor_poly or not seg_line.intersects(corridor_poly):
                    continue

                boundary = corridor_poly.boundary
                p1_in = corridor_poly.contains(Point(p1.lon, p1.lat))
                p2_in = corridor_poly.contains(Point(p2.lon, p2.lat))

                inter = seg_line.intersection(boundary)
                if inter.is_empty:
                    continue

                # Collect intersection points
                cross_points: List[Point] = []
                if isinstance(inter, Point):
                    cross_points.append(inter)
                elif hasattr(inter, "geoms"):
                    for g in inter.geoms:
                        if isinstance(g, Point):
                            cross_points.append(g)
                        elif isinstance(g, LineString):
                            cross_points.append(Point(g.coords[0]))
                            cross_points.append(Point(g.coords[-1]))

                # Sort points along segment from P1 to P2
                cross_points.sort(key=lambda pt: seg_line.project(pt))

                for pt in cross_points:
                    dist_along = seg_line.project(pt)
                    r = max(0.0, min(1.0, dist_along / seg_len_deg))

                    delta_sec = (p2.timestamp - p1.timestamp).total_seconds()
                    crossing_time = p1.timestamp + timedelta(seconds=delta_sec * r)

                    current_state = vessel_states.get(gw.gateway_id, "OUTSIDE")

                    # Classify event based on state transition
                    if current_state == "OUTSIDE":
                        event_type = EventType.ENTRY
                        vessel_states[gw.gateway_id] = "INSIDE"
                    elif current_state == "INSIDE":
                        event_type = EventType.EXIT
                        vessel_states[gw.gateway_id] = "OUTSIDE"
                    else:
                        event_type = EventType.CORRIDOR_CROSSING

                    # Idempotency deduplication key (rounded to minute)
                    key_minute = crossing_time.strftime("%Y%m%d%H%M")
                    dedup_key = f"{track.vessel_id}_{gw.gateway_id}_{event_type.value}_{key_minute}"
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)

                    interp_speed = round(p1.sog + r * (p2.sog - p1.sog), 1)
                    interp_course = round(p1.cog if r < 0.5 else p2.cog, 1)

                    ev_hash = hashlib.sha256(dedup_key.encode("utf-8")).hexdigest()[:8].upper()
                    event = GatewayCrossingEvent(
                        event_id=f"EVT_{ev_hash}",
                        vessel_id=track.vessel_id,
                        vessel_name=track.vessel_name,
                        gateway_id=gw.gateway_id,
                        event_type=event_type,
                        timestamp=crossing_time,
                        latitude=round(pt.y, 5),
                        longitude=round(pt.x, 5),
                        speed_knots=interp_speed,
                        course_deg=interp_course,
                        interpolation_ratio=round(r, 4),
                        source="GATEWAY_INTERSECTION",
                    )
                    events.append(event)

        return events
