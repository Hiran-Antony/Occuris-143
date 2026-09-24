"""
Occuris Module 8 — Merkle Audit Ledger Extension for Ranking Artifacts

Extends the single unified Merkle audit chain (from Module 5 and Module 6)
with forensic RANKING_ARTIFACT records. Every generated RankingBundleV1 is canonicalized,
cryptographically hashed, chained, and anchored.

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.ais.audit import MerkleAuditEngine, canonical_json, compute_row_hash
from src.ais.schemas import AuditVerifyResult
from src.config import DB_PATH
from src.ranking.schemas import RankingBundleV1


def compute_bundle_canonical_hash(bundle: RankingBundleV1) -> str:
    """Compute deterministic SHA-256 hash over canonical representation of ranking bundle."""
    canonical_payload = {
        "case_id": bundle.case_id,
        "module8_version": bundle.module8_version,
        "hypotheses": [
            {"id": h.hypothesis_id, "posterior": round(h.posterior, 4), "status": h.status}
            for h in bundle.hypothesis_posteriors
        ],
        "vessels": [
            {
                "vessel_id": v.vessel_id,
                "prior": round(v.prior, 4),
                "posterior": round(v.posterior, 4),
                "priority": v.priority.value if hasattr(v.priority, "value") else str(v.priority),
                "interval": [round(x, 4) for x in v.posterior_interval],
            }
            for v in bundle.vessels
        ],
        "inspection_plan": [
            {
                "vessel_id": a.vessel_id,
                "order": a.order,
                "value": round(a.value, 4),
                "cost": round(a.cost, 4),
            }
            for a in bundle.inspection_plan
        ],
        "review_queue": bundle.review_queue,
    }
    return canonical_json(canonical_payload)


def record_ranking_artifact(
    bundle: RankingBundleV1,
    audit_engine: Optional[MerkleAuditEngine] = None,
    db_path: Optional[Path] = None,
) -> str:
    """
    Append RANKING_ARTIFACT to the immutable Merkle audit ledger.
    Persists to SQLite audit_events table and updates bundle.ledger_hash.
    """
    if audit_engine is None:
        from src.api.maritime import engine, ensure_pipeline
        ensure_pipeline()
        audit_engine = engine.audit_engine

    canonical_data_str = compute_bundle_canonical_hash(bundle)

    artifact = {
        "event_id": f"RANKING_{bundle.case_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "event_type": "RANKING_ARTIFACT",
        "record_type": "RANKING_ARTIFACT",
        "case_id": bundle.case_id,
        "module8_version": bundle.module8_version,
        "vessel_count": len(bundle.vessels),
        "top_vessel_id": bundle.vessels[0].vessel_id if bundle.vessels else None,
        "top_posterior": bundle.vessels[0].posterior if bundle.vessels else None,
        "budget_utilization": bundle.budget_utilization,
        "canonical_hash": canonical_data_str,
        "timestamp": bundle.generated_at,
    }

    curr_h, prev_h = audit_engine.hash_and_append(artifact)
    bundle.ledger_hash = curr_h

    # Create checkpoint anchor to solidify Merkle root
    audit_engine.create_checkpoint()

    # Persist to SQLite audit_events table
    target_db = db_path or DB_PATH
    try:
        con = sqlite3.connect(target_db)
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT,
                event_type TEXT,
                case_id TEXT,
                timestamp TEXT,
                row_hash TEXT,
                prev_hash TEXT,
                canonical_data TEXT
            )
        """)
        cur.execute("""
            INSERT INTO audit_events (event_id, event_type, case_id, timestamp, row_hash, prev_hash, canonical_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            artifact["event_id"],
            "RANKING_ARTIFACT",
            bundle.case_id,
            bundle.generated_at,
            curr_h,
            prev_h,
            canonical_data_str,
        ))
        con.commit()
        con.close()
    except Exception as ex:
        # Non-fatal persistence logging
        print(f"[Module 8 Audit] SQLite persist note: {ex}")

    return curr_h


def verify_ranking_chain(audit_engine: Optional[MerkleAuditEngine] = None) -> AuditVerifyResult:
    """Verify entire audit ledger and confirm RANKING_ARTIFACT events are cryptographically intact."""
    if audit_engine is None:
        from src.api.maritime import engine, ensure_pipeline
        ensure_pipeline()
        audit_engine = engine.audit_engine

    return audit_engine.verify_ledger()
