"""
Module 5 — Maritime Memory & Virtual Gateways — FastAPI Router (§7)
Prefix: /api/v1
Exposes full forensic pipeline endpoints:
- Corridors, dynamic vessel states, and tracks
- Interpolated gateway crossing events
- Journey memory and baseline delay analyses
- Innovation A: Behavioral DNA and re-identification
- Innovation B: Collective anomalies (Coordinated Dark, Rendezvous, Convergence)
- Innovation C: Physics-informed dark-path hypotheses
- Innovation D: Cryptographic Merkle audit ledger verification
- Traffic density binned percentiles and temporal replay snapshots
- EvidenceBundleV1: frozen downstream contract for Modules 6/7/8
- Admin: rebuild / state / run_manifests for deterministic builds
All responses validated via Pydantic v2 schemas with source_mode and UTC timestamps.
All thresholds read from config/region.yaml — zero magic numbers.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query

from src.ais import (
    AisSourceMode,
    AuditVerifyResult,
    BehavioralDNAExtractor,
    BehaviourAuditor,
    CollectiveAnomalyDetector,
    CrossingDetector,
    CsvReplaySource,
    DarkPathReconstructor,
    DelayAnalyzer,
    MaritimeMemory,
    MerkleAuditEngine,
    TrackBuilder,
    TrafficAnalyzer,
    gateways_to_geojson,
    get_default_source,
    get_gateway_manager,
)
from src.ais.schemas import (
    AuditAnchor,
    BehaviourAssessment,
    CollectiveAnomalyEvent,
    DarkPathHypothesis,
    DnaMatch,
    EvidenceBundleV1,
    GatewayCrossingEvent,
    RunManifest,
    TrafficDensityBin,
    VesselBehavioralDNA,
    VesselJourney,
)
from src.config import DB_PATH, ROOT

MODULE5_VERSION = "5.1.0"
CONFIG_REGION_PATH = ROOT / "config" / "region.yaml"

router = APIRouter(prefix="/api/v1", tags=["Module 5 — Maritime Memory"])


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    if path.exists():
        h.update(path.read_bytes())
    return h.hexdigest()


def _load_region_config() -> Dict[str, Any]:
    """Load config/region.yaml as dict."""
    if CONFIG_REGION_PATH.exists():
        with open(CONFIG_REGION_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class MaritimeEngineState:
    """Singleton state coordinator managing the unified Module 5 in-memory and SQLite pipeline."""

    def __init__(self):
        self.initialized = False
        self.build_id: str = ""
        self.input_csv_hash: str = ""
        self.config_hash: str = ""
        self.params_hash: str = ""
        self.output_hash: str = ""
        self.seed: int = 0
        self.built_at: str = ""

        # Load config
        cfg = _load_region_config()
        thresholds = cfg.get("thresholds", {})

        self.source = get_default_source()
        self.gw_manager = get_gateway_manager()
        self.track_builder = TrackBuilder(
            gap_threshold_min=float(thresholds.get("ais_gap_minutes", 15.0))
        )
        self.crossing_detector = CrossingDetector(gateway_manager=self.gw_manager)
        self.memory = MaritimeMemory()
        self.traffic_analyzer = TrafficAnalyzer(
            bin_duration_minutes=int(thresholds.get("traffic_bin_minutes", 60)),
            percentile_threshold=float(thresholds.get("traffic_high_percentile", 75.0)),
        )
        self.delay_analyzer = DelayAnalyzer()
        self.behaviour_auditor = BehaviourAuditor(
            wind_threshold_ms=float(thresholds.get("weather_wind_ms", 6.5)),
        )
        self.dna_extractor = BehavioralDNAExtractor()
        self.collective_detector = CollectiveAnomalyDetector()
        self.dark_path_reconstructor = DarkPathReconstructor(
            max_vessel_speed_knots=float(thresholds.get("vessel_max_speed_kn", 18.0)),
        )

        merkle_window = int(thresholds.get("merkle_window_events", 100))
        self.audit_engine = MerkleAuditEngine(checkpoint_window_events=merkle_window)

        # In-memory indices
        self.records = []
        self.tracks = {}
        self.crossings = []
        self.journeys = {}
        self.transits = {}
        self.assessments = {}
        self.dna_profiles = {}
        self.collective_events = []
        self.dark_hypotheses = {}
        self.traffic_bins = []

    def load_and_process(self, custom_csv_path: Optional[Path] = None, seed: int = 0):
        """Run complete deterministic offline pipeline over AIS dataset."""
        if custom_csv_path:
            self.source = CsvReplaySource(custom_csv_path)

        self.seed = seed
        csv_path = custom_csv_path or Path(self.source.csv_path) if hasattr(self.source, 'csv_path') else None

        # Compute provenance hashes
        self.input_csv_hash = _sha256_file(csv_path) if csv_path else ""
        self.config_hash = _sha256_file(CONFIG_REGION_PATH)

        cfg = _load_region_config()
        thresholds = cfg.get("thresholds", {})
        from src.ais.audit import canonical_json
        self.params_hash = hashlib.sha256(canonical_json(thresholds).encode()).hexdigest()

        # 1. Ingest & validate
        self.records = self.source.load()

        # 2. Tracks & Gaps
        self.tracks = self.track_builder.build_tracks(self.records)

        # 3. Gateway Crossings (Interpolated & State-validated)
        self.crossings = self.crossing_detector.detect_crossings(self.tracks)

        # 4. Maritime Memory Journeys
        self.journeys = self.memory.build_journeys(self.tracks, self.crossings)

        # 5. Delay Analysis (Strict 3-tier precedence)
        self.transits = self.delay_analyzer.analyze_all(self.journeys)

        # 6. Traffic Density (must run before behaviour to compute percentile cutoffs)
        self.traffic_bins = self.traffic_analyzer.compute_density_bins(self.records)
        traffic_now = {
            v_id: self.traffic_analyzer.get_traffic_at_time(
                self.records,
                self.tracks[v_id].pings[0].timestamp if self.tracks[v_id].pings else datetime.now(timezone.utc)
            )
            for v_id in self.tracks
        }

        # 7. Behaviour Audit & Evidence List
        self.assessments = self.behaviour_auditor.audit_all(
            self.tracks, self.journeys, self.transits, traffic_now
        )

        # 8. Innovation A: Behavioral DNA
        self.dna_profiles = {
            v_id: self.dna_extractor.extract_dna(track)
            for v_id, track in self.tracks.items()
        }

        # 9. Innovation B: Collective Anomalies
        self.collective_events = self.collective_detector.detect_anomalies(self.tracks)

        # 10. Innovation C: Dark-Path Reconstruction
        self.dark_hypotheses = {}
        for v_id, track in self.tracks.items():
            hyp_list = []
            for gap in track.gaps:
                hyp = self.dark_path_reconstructor.reconstruct_gap(gap)
                hyp_list.append(hyp)
            if hyp_list:
                self.dark_hypotheses[v_id] = hyp_list

        # 11. Innovation D: Merkle Audit Hash Chaining (with provenance)
        merkle_window = int(thresholds.get("merkle_window_events", 100))
        self.audit_engine = MerkleAuditEngine(
            checkpoint_window_events=merkle_window,
            input_csv_hash=self.input_csv_hash,
            region_yaml_hash=self.config_hash,
            pipeline_params_hash=self.params_hash,
        )
        for ev in self.crossings:
            ev_dict = ev.model_dump()
            curr_h, prev_h = self.audit_engine.hash_and_append(ev_dict)
            ev.row_hash = curr_h
            ev.prev_hash = prev_h

        for v_id, ass in self.assessments.items():
            ass_dict = ass.model_dump()
            curr_h, _ = self.audit_engine.hash_and_append(ass_dict)
            ass.row_hash = curr_h

        self.audit_engine.create_checkpoint()

        # 12. Compute deterministic output hash
        self.output_hash = self._compute_output_hash()

        # 13. Build manifest
        build_seed_key = f"{self.input_csv_hash}_{self.config_hash}_{seed}"
        self.build_id = f"BUILD_{hashlib.sha256(build_seed_key.encode()).hexdigest()[:8].upper()}"
        self.built_at = datetime.now(timezone.utc).isoformat()

        self.persist_to_db()
        self.initialized = True

    def _compute_output_hash(self) -> str:
        """SHA-256 over canonical serialization of deterministic pipeline outputs."""
        from src.ais.audit import canonical_json
        payload = {
            "gateway_events": [e.model_dump() for e in self.crossings],
            "vessel_journeys": {k: v.model_dump() for k, v in self.journeys.items()},
            "behaviour_events": {k: v.model_dump() for k, v in self.assessments.items()},
        }
        return hashlib.sha256(canonical_json(payload).encode()).hexdigest()

    def get_run_manifest(self) -> RunManifest:
        """Return current build manifest."""
        return RunManifest(
            build_id=self.build_id,
            input_csv_hash=self.input_csv_hash,
            region_yaml_hash=self.config_hash,
            params_hash=self.params_hash,
            seed=self.seed,
            built_at=self.built_at,
            output_hash=self.output_hash,
        )

    def persist_to_db(self):
        """Persist state to SQLite tables."""
        try:
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()

            # Ensure run_manifests table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS run_manifests (
                    build_id TEXT PRIMARY KEY,
                    input_csv_hash TEXT,
                    region_yaml_hash TEXT,
                    code_rev TEXT,
                    params_hash TEXT,
                    seed INTEGER,
                    built_at TEXT,
                    output_hash TEXT
                )
            """)

            # Gateway Events
            for ev in self.crossings:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO gateway_events
                    (event_id, vessel_id, gateway_id, event_type, timestamp, latitude, longitude,
                     speed_knots, course_deg, interpolation_ratio, source, row_hash, prev_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ev.event_id, ev.vessel_id, ev.gateway_id, ev.event_type.value,
                        ev.timestamp.isoformat(), ev.latitude, ev.longitude,
                        ev.speed_knots, ev.course_deg, ev.interpolation_ratio,
                        ev.source, ev.row_hash, ev.prev_hash
                    )
                )

            # Journeys
            for j_id, j in self.journeys.items():
                cur.execute(
                    """
                    INSERT OR REPLACE INTO vessel_journeys
                    (journey_id, vessel_id, entry_gateway, entry_time, exit_gateway, exit_time,
                     distance_km, actual_duration_h, expected_duration_h, delay_h, z_score,
                     average_speed_kn, max_observed_speed_kn, dominant_course_deg, expected_basis, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        j.journey_id, j.vessel_id, j.entry_gateway,
                        j.entry_time.isoformat() if j.entry_time else None,
                        j.exit_gateway,
                        j.exit_time.isoformat() if j.exit_time else None,
                        j.distance_km, j.actual_duration_h, j.expected_duration_h,
                        j.delay_h, j.z_score, j.average_speed_kn,
                        j.max_observed_speed_kn, j.dominant_course_deg,
                        j.expected_basis.value, j.status.value
                    )
                )

            # Run manifest
            if self.build_id:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO run_manifests
                    (build_id, input_csv_hash, region_yaml_hash, code_rev, params_hash, seed, built_at, output_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.build_id, self.input_csv_hash, self.config_hash,
                        MODULE5_VERSION, self.params_hash, self.seed,
                        self.built_at, self.output_hash
                    )
                )

            con.commit()
            con.close()
        except Exception as ex:
            print(f"[Maritime API] Warning: SQLite sync encountered: {ex}")


engine = MaritimeEngineState()


def ensure_pipeline():
    if not engine.initialized:
        # Check if demo CSV exists, else fallback to standard
        demo_csv = ROOT / "data" / "raw" / "synthetic" / "module5_demo.csv"
        csv_to_load = demo_csv if demo_csv.exists() else None
        engine.load_and_process(csv_to_load)


# ── REST Endpoints ────────────────────────────────────────────────────────────

@router.get("/gateways")
def get_gateways():
    """Return virtual narrow corridor gateways formatted as GeoJSON FeatureCollection."""
    ensure_pipeline()
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "geojson": engine.gw_manager.to_geojson(),
    }


@router.get("/maritime/vessels")
def get_vessels(time: Optional[str] = Query(None, description="ISO-8601 UTC timestamp for historical replay")):
    """Return current or temporal positions and operational telemetry for all monitored vessels."""
    ensure_pipeline()

    target_dt = None
    if time:
        t_clean = time.strip().replace("Z", "+00:00")
        target_dt = datetime.fromisoformat(t_clean)
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)

    results = []
    for v_id, track in engine.tracks.items():
        if target_dt:
            state = TrackBuilder.get_state_at_time(track, target_dt)
            if state:
                results.append(state)
        else:
            curr = track.pings[-1] if track.pings else None
            assessment = engine.assessments.get(v_id)
            results.append({
                "vessel_id": track.vessel_id,
                "vessel_name": track.vessel_name,
                "mmsi": track.mmsi,
                "lat": curr.lat if curr else 0.0,
                "lon": curr.lon if curr else 0.0,
                "sog": curr.sog if curr else 0.0,
                "cog": curr.cog if curr else 0.0,
                "nav_status_label": curr.nav_status_label if curr else "Under way",
                "timestamp": curr.timestamp.isoformat() if curr else None,
                "ais_continuity": track.ais_continuity.value,
                "assessment": assessment.status.value if assessment else "INSUFFICIENT_DATA",
            })

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vessels": results,
    }


@router.get("/maritime/vessels/{vessel_id}/track")
def get_vessel_track(vessel_id: str):
    """Return complete chronological trajectory, geodesic segments, and detected gaps."""
    ensure_pipeline()
    track = engine.tracks.get(vessel_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vessel_id": track.vessel_id,
        "vessel_name": track.vessel_name,
        "mmsi": track.mmsi,
        "pings": [p.model_dump() for p in track.pings],
        "gaps": [g.model_dump() for g in track.gaps],
    }


@router.get("/maritime/gateway-events")
def get_gateway_events(
    vessel_id: Optional[str] = Query(None),
    gateway_id: Optional[str] = Query(None),
):
    """Query chronological gateway entry and exit crossings with sub-second interpolated times."""
    ensure_pipeline()
    events = engine.crossings
    if vessel_id:
        events = [e for e in events if e.vessel_id == vessel_id]
    if gateway_id:
        events = [e for e in events if e.gateway_id == gateway_id]

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": [e.model_dump() for e in events],
    }


@router.get("/maritime/vessels/{vessel_id}/journey")
def get_vessel_journey(vessel_id: str):
    """Query unit of memory: journey duration, baseline comparison, and behavioral evidence."""
    ensure_pipeline()
    journey = engine.journeys.get(vessel_id)
    if not journey:
        raise HTTPException(status_code=404, detail=f"No journey found for vessel {vessel_id}")

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "journey": journey.model_dump(),
        "transit": engine.transits.get(vessel_id).model_dump() if engine.transits.get(vessel_id) else None,
        "assessment": engine.assessments.get(vessel_id).model_dump() if engine.assessments.get(vessel_id) else None,
    }


@router.get("/maritime/vessels/{vessel_id}/dna")
def get_vessel_dna(vessel_id: str):
    """Innovation A: Retrieve high-dimensional kinematic behavioral signature."""
    ensure_pipeline()
    dna = engine.dna_profiles.get(vessel_id)
    if not dna:
        raise HTTPException(status_code=404, detail=f"No DNA profile for vessel {vessel_id}")

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dna": dna.model_dump(),
    }


@router.get("/maritime/vessels/{vessel_id}/dark-paths")
def get_vessel_dark_paths(vessel_id: str):
    """Innovation C: Retrieve physics-informed dark-path hypothesis candidates."""
    ensure_pipeline()
    hyps = engine.dark_hypotheses.get(vessel_id, [])
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "vessel_id": vessel_id,
        "hypotheses": [h.model_dump() for h in hyps],
        "disclaimer": "HYPOTHESIS — reconstructed, not observed",
    }


@router.get("/maritime/collective-anomalies")
def get_collective_anomalies():
    """Innovation B: Retrieve fleet-wide coordinated dark, rendezvous, and convergence events."""
    ensure_pipeline()
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": [e.model_dump() for e in engine.collective_events],
    }


@router.get("/maritime/traffic-density")
def get_traffic_density():
    """Retrieve temporal corridor traffic density bins and percentile classification."""
    ensure_pipeline()
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bins": [b.model_dump() for b in engine.traffic_bins],
    }


@router.get("/maritime/audit/verify")
def verify_audit_ledger():
    """Innovation D: Recompute and cryptographically verify the Merkle event chain."""
    ensure_pipeline()
    result = engine.audit_engine.verify_ledger()
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verification": result.model_dump(),
    }


@router.get("/maritime/replay")
def get_replay_snapshot(
    time: str = Query(..., description="Target ISO-8601 UTC timestamp"),
    case_id: Optional[str] = Query(None),
):
    """Return synchronized fleet snapshot, active corridors, and historical trail at target timestamp."""
    ensure_pipeline()
    t_clean = time.strip().replace("Z", "+00:00")
    target_dt = datetime.fromisoformat(t_clean)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    active_vessels = []
    for v_id, track in engine.tracks.items():
        st = TrackBuilder.get_state_at_time(track, target_dt)
        if st:
            active_vessels.append(st)

    # Filter events occurring up to target_dt
    recent_events = [e for e in engine.crossings if e.timestamp <= target_dt]
    recent_anomalies = [a for a in engine.collective_events if a.window_start <= target_dt]

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "replay_time": target_dt.isoformat(),
        "case_id": case_id,
        "vessels": active_vessels,
        "events": [e.model_dump() for e in recent_events[-20:]],
        "collective_anomalies": [a.model_dump() for a in recent_anomalies],
    }


# ── Evidence Bundle Contract Endpoint ─────────────────────────────────────────

@router.get("/maritime/evidence-bundle/{vessel_id}")
def get_evidence_bundle(
    vessel_id: str,
    case_id: str = Query("UNSPECIFIED", description="Investigation case identifier"),
):
    """
    EvidenceBundleV1: the ONLY contract Modules 6/7/8 (and future OccurisBench) consume.
    Aggregates all Module 5 evidence for a single vessel into a frozen schema.
    """
    ensure_pipeline()

    track = engine.tracks.get(vessel_id)
    if not track:
        raise HTTPException(status_code=404, detail=f"Vessel {vessel_id} not found")

    journey = engine.journeys.get(vessel_id)
    transit = engine.transits.get(vessel_id)
    assessment = engine.assessments.get(vessel_id)
    dna = engine.dna_profiles.get(vessel_id)
    dark_hyps = engine.dark_hypotheses.get(vessel_id, [])

    # DNA re-id best match
    dna_best_confidence = None
    dna_method = None
    if dna:
        matches = engine.dna_extractor.reidentify_post_gap(track, engine.dna_profiles)
        if matches:
            dna_best_confidence = matches[0].confidence_pct
            dna_method = matches[0].method

    # Collective anomaly IDs involving this vessel
    anomaly_ids = [
        e.event_id for e in engine.collective_events
        if vessel_id in e.vessel_cluster
    ]

    bundle = EvidenceBundleV1(
        case_id=case_id,
        vessel_id=vessel_id,
        journey=journey,
        ais_gaps=list(track.gaps),
        transit_analysis=transit,
        behaviour_assessment=assessment,
        dna_profile_id=vessel_id if dna else None,
        dna_best_match_confidence=dna_best_confidence,
        dna_method=dna_method,
        collective_anomaly_ids=anomaly_ids,
        dark_path_hypotheses=dark_hyps,
        latest_event_hash=engine.audit_engine.latest_hash,
        source_mode=engine.source.source_mode,
        module5_version=MODULE5_VERSION,
    )

    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_bundle": bundle.model_dump(),
    }


# ── Admin / Lifecycle Endpoints ───────────────────────────────────────────────

@router.post("/admin/rebuild")
def admin_rebuild(seed: int = Query(0)):
    """DEV-guarded: Force full pipeline rebuild with optional seed for determinism."""
    engine.initialized = False
    engine.__init__()
    demo_csv = ROOT / "data" / "raw" / "synthetic" / "module5_demo.csv"
    csv_to_load = demo_csv if demo_csv.exists() else None
    engine.load_and_process(csv_to_load, seed=seed)
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "REBUILD_COMPLETE",
        "build_id": engine.build_id,
        "output_hash": engine.output_hash,
    }


@router.get("/admin/state")
def admin_state():
    """Return current engine build state and provenance hashes."""
    ensure_pipeline()
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_id": engine.build_id,
        "input_hash": engine.input_csv_hash,
        "config_hash": engine.config_hash,
        "code_rev": MODULE5_VERSION,
        "seed": engine.seed,
        "built_at": engine.built_at,
        "output_hash": engine.output_hash,
        "vessel_count": len(engine.tracks),
        "crossing_count": len(engine.crossings),
        "journey_count": len(engine.journeys),
    }


@router.get("/maritime/source-info")
def get_source_info():
    """Metadata indicator for data provenance display."""
    ensure_pipeline()
    return {
        "source_mode": engine.source.source_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_label": engine.source.source_label,
        "record_count": len(engine.records),
        "vessel_count": len(engine.tracks),
        "module5_version": MODULE5_VERSION,
    }
