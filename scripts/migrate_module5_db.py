"""
Module 5 — Database Schema Migration
Creates PostgreSQL/PostGIS compatible SQLite tables for Module 5 Maritime Memory,
including behavioral DNA, collective anomaly events, dark-path hypotheses, and Merkle audit anchors.
"""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "occris.db"


def run_migration():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Enable foreign keys
    cur.execute("PRAGMA foreign_keys = ON;")

    cur.executescript("""
    -- 1. Gateway Crossing Events (Tamper-evident hash chained)
    CREATE TABLE IF NOT EXISTS gateway_events (
        event_id            TEXT PRIMARY KEY,
        vessel_id           TEXT NOT NULL,
        gateway_id          TEXT NOT NULL,
        event_type          TEXT NOT NULL,   -- 'ENTRY' / 'EXIT' / 'CORRIDOR_CROSSING'
        timestamp           TEXT NOT NULL,   -- ISO-8601 UTC
        latitude            REAL NOT NULL,
        longitude           REAL NOT NULL,
        speed_knots         REAL NOT NULL,
        course_deg          REAL NOT NULL,
        interpolation_ratio REAL NOT NULL,
        source              TEXT DEFAULT 'AIS_PROCESSING',
        row_hash            TEXT,
        prev_hash           TEXT,
        created_at          TEXT DEFAULT (datetime('now'))
    );

    -- 2. Vessel Journeys (Unit of Memory)
    CREATE TABLE IF NOT EXISTS vessel_journeys (
        journey_id              TEXT PRIMARY KEY,
        vessel_id               TEXT NOT NULL,
        entry_gateway           TEXT,
        entry_time              TEXT,
        exit_gateway            TEXT,
        exit_time               TEXT,
        distance_km             REAL NOT NULL,
        actual_duration_h       REAL NOT NULL,
        expected_duration_h     REAL,
        delay_h                 REAL,
        z_score                 REAL,
        average_speed_kn        REAL,
        max_observed_speed_kn   REAL,
        dominant_course_deg     REAL,
        expected_basis          TEXT NOT NULL,  -- 'HISTORICAL' / 'CORRIDOR_BASELINE' / 'INSUFFICIENT_HISTORY'
        status                  TEXT NOT NULL   -- 'COMPLETED' / 'IN_REGION' / 'PARTIAL_ENTRY_ONLY' / 'PARTIAL_EXIT_ONLY'
    );

    -- 3. Behaviour Events (Tamper-evident hash chained)
    CREATE TABLE IF NOT EXISTS behaviour_events (
        event_id        TEXT PRIMARY KEY,
        vessel_id       TEXT NOT NULL,
        timestamp       TEXT NOT NULL,
        event_type      TEXT NOT NULL,  -- 'NORMAL_TRANSIT' / 'EXPLAINED_DELAY' / 'POTENTIAL_UNEXPLAINED_DELAY' / 'INSUFFICIENT_DATA'
        severity        TEXT NOT NULL,  -- 'INFO' / 'LOW' / 'MEDIUM' / 'HIGH'
        reason          TEXT NOT NULL,
        evidence_json   TEXT NOT NULL,  -- List of tested factor explanations
        row_hash        TEXT,
        prev_hash       TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );

    -- 4. Innovation A: Vessel Behavioral DNA
    CREATE TABLE IF NOT EXISTS vessel_behavioral_dna (
        vessel_id            TEXT PRIMARY KEY,
        feature_vector_json  TEXT NOT NULL,
        covariance_json      TEXT,
        sample_count         INTEGER NOT NULL,
        confidence           REAL NOT NULL,
        updated_at           TEXT DEFAULT (datetime('now'))
    );

    -- 5. Innovation B: Collective Anomaly Events
    CREATE TABLE IF NOT EXISTS collective_anomaly_events (
        event_id              TEXT PRIMARY KEY,
        vessel_cluster_json   TEXT NOT NULL, -- list of vessel IDs
        anomaly_type          TEXT NOT NULL, -- 'COORDINATED_DARK' / 'RENDEZVOUS' / 'CONVERGENCE'
        window_start          TEXT NOT NULL,
        window_end            TEXT NOT NULL,
        evidence_json         TEXT NOT NULL,
        created_at            TEXT DEFAULT (datetime('now'))
    );

    -- 6. Innovation C: Physics-Informed Dark-Path Hypotheses
    CREATE TABLE IF NOT EXISTS dark_path_hypotheses (
        hypothesis_id      TEXT PRIMARY KEY,
        vessel_id          TEXT NOT NULL,
        gap_start          TEXT NOT NULL,
        gap_end            TEXT NOT NULL,
        paths_json         TEXT NOT NULL, -- list of candidate paths with probabilities
        intersects_origin  INTEGER NOT NULL DEFAULT 0,
        created_at         TEXT DEFAULT (datetime('now'))
    );

    -- 7. Innovation D: Merkle Audit Anchors
    CREATE TABLE IF NOT EXISTS audit_anchors (
        anchor_id       TEXT PRIMARY KEY,
        merkle_root     TEXT NOT NULL,
        event_count     INTEGER NOT NULL,
        window_start    TEXT NOT NULL,
        window_end      TEXT NOT NULL,
        external_tx_id  TEXT,
        created_at      TEXT DEFAULT (datetime('now'))
    );

    -- Composite Performance & Foreign Query Indexes
    CREATE INDEX IF NOT EXISTS idx_gateway_events_vessel_time ON gateway_events(vessel_id, timestamp);
    CREATE INDEX IF NOT EXISTS idx_gateway_events_gw_type ON gateway_events(gateway_id, event_type);
    CREATE INDEX IF NOT EXISTS idx_behaviour_events_vessel_time ON behaviour_events(vessel_id, timestamp);
    CREATE INDEX IF NOT EXISTS idx_vessel_journeys_vessel ON vessel_journeys(vessel_id);
    CREATE INDEX IF NOT EXISTS idx_collective_window ON collective_anomaly_events(window_start, window_end);
    CREATE INDEX IF NOT EXISTS idx_dark_path_vessel ON dark_path_hypotheses(vessel_id);
    """)

    con.commit()
    con.close()
    print(f"[Module 5 DB] Migrations successfully applied to {DB_PATH}")


if __name__ == "__main__":
    run_migration()
