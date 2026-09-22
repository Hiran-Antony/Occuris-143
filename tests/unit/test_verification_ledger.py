"""
Module 6 — Unit Tests: Merkle Audit Ledger Integration
Tests extending Module 5 audit chain with VERIFICATION_ARTIFACT records,
verifying full chain integrity, and detecting tampering.
"""

import pytest
from datetime import datetime, timezone

from src.ais.audit import MerkleAuditEngine, GENESIS_HASH


def test_extend_audit_chain_with_module6_artifact():
    """Extend Module 5 Merkle chain with VERIFICATION_ARTIFACT records."""
    engine = MerkleAuditEngine(checkpoint_window_events=3)

    # Ingest standard Module 5 events
    engine.hash_and_append({
        "event_id": "EVT_001",
        "vessel_id": "V_NORMAL",
        "event_type": "ENTRY",
        "timestamp": datetime(2024, 3, 15, 6, 0, tzinfo=timezone.utc).isoformat(),
    })

    # Ingest Module 6 verification artifact
    h1, prev1 = engine.hash_and_append({
        "record_type": "VERIFICATION_ARTIFACT",
        "case_id": "case_01",
        "vessel_id": "V_NORMAL",
        "ais_state": "NORMAL",
        "integrity_score": 0.982,
        "module6_version": "6.0.0",
        "anomaly_count": 0,
    })

    assert len(h1) == 64
    assert prev1 != GENESIS_HASH

    # Ingest second Module 6 artifact
    h2, prev2 = engine.hash_and_append({
        "record_type": "VERIFICATION_ARTIFACT",
        "case_id": "case_01",
        "vessel_id": "V_GAP",
        "ais_state": "AIS_GAP_DARK",
        "integrity_score": 0.45,
        "module6_version": "6.0.0",
        "anomaly_count": 1,
    })

    assert prev2 == h1
    assert len(engine.chained_events) == 3
    # Checkpoint should be created at window=3
    assert len(engine.anchors) == 1

    # Full chain verify
    res = engine.verify_ledger()
    assert res.verified is True
    assert res.status == "VERIFY_SUCCESS"
    assert res.total_events == 3


def test_module6_artifact_tamper_detection():
    """Tampering with a VERIFICATION_ARTIFACT in the Merkle chain triggers VERIFY_FAILED."""
    engine = MerkleAuditEngine(checkpoint_window_events=5)

    for i in range(4):
        engine.hash_and_append({
            "record_type": "VERIFICATION_ARTIFACT",
            "case_id": "case_01",
            "vessel_id": f"V00{i}",
            "ais_state": "NORMAL",
            "integrity_score": 0.9,
            "module6_version": "6.0.0",
        })

    # Tamper with record at index 2 (e.g. change integrity_score or ais_state)
    engine.chained_events[2]["integrity_score"] = 0.123

    res = engine.verify_ledger()
    assert res.verified is False
    assert res.status == "VERIFY_FAILED"
    assert res.broken_chain_at == "row_2"
