"""
Module 5 — Maritime Memory & Virtual Gateways — FastAPI Router
Endpoints for virtual gateways, vessel trajectories, gateway events,
transit analysis, and behaviour classification.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.ais import (
    AISSourceMode,
    BehaviourClassifier,
    CrossingDetector,
    DelayAnalyzer,
    MaritimeMemory,
    SourceInfo,
    TrackBuilder,
    TrafficAnalyzer,
    gateways_to_geojson,
    get_default_adapter,
    get_default_gateways,
)
from src.ais.schemas import (
    BehaviourAssessment,
    GatewayCrossingEvent,
    SourceInfo,
    VesselJourney,
)
from src.config import DB_PATH

router = APIRouter(prefix="/api", tags=["maritime"])

# ── Maritime State Singleton / Cache ──────────────────────────────────────────
class MaritimeState:
    def __init__(self):
        self.initialized = False
        self.adapter = get_default_adapter()
        self.gateways = get_default_gateways()
        self.track_builder = TrackBuilder()
        self.crossing_detector = CrossingDetector()
        self.memory = MaritimeMemory()
        self.delay_analyzer = DelayAnalyzer()
        self.traffic_analyzer = TrafficAnalyzer()
        self.behaviour_classifier = BehaviourClassifier()

        self.records = []
        self.tracks = {}
        self.crossings = []
        self.journeys = {}
        self.transits = {}
        self.assessments = {}

    def initialize(self):
        if self.initialized:
            return

        # 1. Load AIS records
        self.records = self.adapter.load()

        # 2. Build tracks & detect gaps
        self.tracks = self.track_builder.build_tracks(self.records)

        # 3. Detect gateway crossings
        self.crossings = self.crossing_detector.detect_crossings(self.tracks, self.gateways)

        # 4. Construct journeys
        self.journeys = self.memory.build_journeys(self.tracks, self.crossings)

        # 5. Analyze transit times
        self.transits = self.delay_analyzer.analyze_all(self.journeys)

        # 6. Evaluate traffic density
        traffic_now = {}
        for v_id, journey in self.journeys.items():
            ref_time = journey.entry_time or (self.tracks[v_id].pings[0].timestamp if self.tracks[v_id].pings else datetime.now())
            traffic_now[v_id] = self.traffic_analyzer.get_traffic_at_time(self.records, ref_time)

        # 7. Multi-factor behaviour assessment
        self.assessments = self.behaviour_classifier.assess_all(
            self.tracks, self.journeys, self.transits, traffic_now
        )

        # 8. Persist to SQLite
        self.persist_to_db()

        self.initialized = True

    def persist_to_db(self):
        """Populate database tables with current session data."""
        try:
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()

            # Vessels
            for v_id, track in self.tracks.items():
                cur.execute(
                    "INSERT OR REPLACE INTO vessels (vessel_id, mmsi, name) VALUES (?, ?, ?)",
                    (v_id, track.mmsi, track.vessel_name),
                )

            # Gateway events
            for ev in self.crossings:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO gateway_events
                    (id, vessel_id, vessel_name, gateway_id, event_type, timestamp, lat, lon, speed, course, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ev.event_id,
                        ev.vessel_id,
                        ev.vessel_name,
                        ev.gateway_id,
                        ev.event_type.value,
                        ev.timestamp.isoformat(),
                        ev.lat,
                        ev.lon,
                        ev.speed,
                        ev.course,
                        ev.source,
                    ),
                )

            # Vessel journeys
            for j_id, j in self.journeys.items():
                cur.execute(
                    """
                    INSERT OR REPLACE INTO vessel_journeys
                    (id, vessel_id, vessel_name, entry_gateway, entry_time, exit_gateway, exit_time,
                     distance_km, actual_duration_h, expected_duration_h, average_speed_kn,
                     max_speed_kn, delay_h, delay_zscore, expected_basis, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        j.journey_id,
                        j.vessel_id,
                        j.vessel_name,
                        j.entry_gateway,
                        j.entry_time.isoformat() if j.entry_time else None,
                        j.exit_gateway,
                        j.exit_time.isoformat() if j.exit_time else None,
                        j.distance_km,
                        j.actual_duration_h,
                        j.expected_duration_h,
                        j.average_speed_kn,
                        j.max_speed_kn,
                        j.delay_h,
                        j.delay_zscore,
                        j.expected_basis.value,
                        j.status.value,
                    ),
                )

            con.commit()
            con.close()
        except Exception as ex:
            print(f"[MaritimeDB] Warning: DB sync encountered error: {ex}")


state = MaritimeState()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/gateways", response_model=Dict[str, Any])
def get_gateways():
    """Returns virtual gateway corridors formatted as GeoJSON."""
    state.initialize()
    return gateways_to_geojson(state.gateways)


@router.get("/maritime/source-info", response_model=SourceInfo)
def get_source_info():
    """Returns metadata about the active AIS stream (synthetic vs live)."""
    state.initialize()
    t_min = min((r.timestamp for r in state.records), default=None)
    t_max = max((r.timestamp for r in state.records), default=None)

    return SourceInfo(
        mode=state.adapter.source_mode,
        label=state.adapter.source_label,
        record_count=len(state.records),
        vessel_count=len(state.tracks),
        time_range_start=t_min,
        time_range_end=t_max,
    )


@router.get("/maritime/vessels")
def get_vessels():
    """Returns latest observed states for all vessels."""
    state.initialize()
    vessels = []
    for v_id, track in state.tracks.items():
        curr = track.current_position
        assessment = state.assessments.get(v_id)
        journey = state.journeys.get(v_id)
        vessels.append({
            "vessel_id": track.vessel_id,
            "vessel_name": track.vessel_name,
            "mmsi": track.mmsi,
            "current_lat": curr.lat if curr else None,
            "current_lon": curr.lon if curr else None,
            "sog": curr.sog if curr else 0.0,
            "cog": curr.cog if curr else 0.0,
            "nav_status_label": curr.nav_status_label if curr else "Under way using engine",
            "last_timestamp": curr.timestamp.isoformat() if curr else None,
            "ping_count": track.ping_count,
            "ais_continuity": track.ais_continuity.value,
            "gaps": [g.model_dump() for g in track.gaps],
            "status": assessment.status.value if assessment else "INSUFFICIENT_DATA",
            "journey_id": journey.journey_id if journey else None,
        })
    return vessels


@router.get("/maritime/vessels/{vessel_id}/track")
def get_vessel_track(vessel_id: str):
    """Returns the full chronological AIS trajectory and gaps for a specific vessel."""
    state.initialize()
    track = state.tracks.get(vessel_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")

    return {
        "vessel_id": track.vessel_id,
        "vessel_name": track.vessel_name,
        "mmsi": track.mmsi,
        "ping_count": track.ping_count,
        "ais_continuity": track.ais_continuity.value,
        "pings": [
            {
                "lat": p.lat,
                "lon": p.lon,
                "timestamp": p.timestamp.isoformat(),
                "sog": p.sog,
                "cog": p.cog,
                "nav_status": p.nav_status,
                "nav_status_label": p.nav_status_label,
            }
            for p in track.pings
        ],
        "gaps": [g.model_dump() for g in track.gaps],
    }


@router.get("/maritime/gateway-events", response_model=List[GatewayCrossingEvent])
def get_gateway_events():
    """Returns all detected gateway crossing events chronologically."""
    state.initialize()
    return state.crossings


@router.get("/maritime/journeys", response_model=List[VesselJourney])
def get_all_journeys():
    """Returns all synthesized vessel journeys."""
    state.initialize()
    return list(state.journeys.values())


@router.get("/maritime/vessels/{vessel_id}/journey")
def get_vessel_journey(vessel_id: str):
    """Returns journey details, transit baseline metrics, and behaviour assessment for a vessel."""
    state.initialize()
    journey = state.journeys.get(vessel_id)
    if not journey:
        raise HTTPException(status_code=404, detail=f"Journey for {vessel_id} not found")

    assessment = state.assessments.get(vessel_id)
    transit = state.transits.get(vessel_id)

    return {
        "journey": journey,
        "transit": transit,
        "assessment": assessment,
    }


@router.get("/maritime/replay", response_model=List[Dict[str, Any]])
def get_replay_state(time: str = Query(..., description="Target ISO timestamp for replay")):
    """
    Returns the positions and historical trails of all vessels active at or prior to
    the given target timestamp.
    """
    state.initialize()
    try:
        t_str = time.strip()
        if t_str.endswith("Z"):
            t_str = t_str[:-1] + "+00:00"
        target_dt = datetime.fromisoformat(t_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISO timestamp format")

    states: List[Dict[str, Any]] = []
    for v_id, track in state.tracks.items():
        v_state = TrackBuilder.get_state_at_time(track, target_dt)
        if v_state:
            states.append(v_state)

    return states


@router.get("/maritime/behaviour", response_model=Dict[str, BehaviourAssessment])
def get_behaviour():
    """Returns multi-factor behaviour assessment for each vessel."""
    state.initialize()
    return state.assessments


@router.get("/maritime/traffic")
def get_traffic():
    """Returns traffic density timeline and overall statistics."""
    state.initialize()
    timeline = state.traffic_analyzer.compute_timeline(state.records, step_minutes=30)
    return {
        "summary": {
            "total_records": len(state.records),
            "monitored_vessels": len(state.tracks),
        },
        "timeline": [
            {
                "time": ctx.time_window_end.isoformat() if ctx.time_window_end else None,
                "vessel_count": ctx.vessel_count,
                "level": ctx.level.value,
            }
            for ctx in timeline
        ],
    }
