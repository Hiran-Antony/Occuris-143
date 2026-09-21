"""Unit tests for src/ais/audit.py."""

from datetime import datetime, timezone
import pytest

from src.ais.audit import (
    GENESIS_HASH,
    MerkleAuditEngine,
    build_merkle_root,
    compute_row_hash,
)
from src.ais.schemas import EventType, GatewayCrossingEvent


def make_event(ev_id: str, prev: str = GENESIS_HASH):
    ev = GatewayCrossingEvent(
        event_id=ev_id,
        vessel_id="V_AUDIT",
        gateway_id="GATE_A",
        event_type=EventType.ENTRY,
        timestamp=datetime(2024, 3, 15, 12, 0, tzinfo=timezone.utc),
        latitude=16.0,
        longitude=65.0,
        prev_hash=prev,
    )
    ev.row_hash = compute_row_hash(ev, prev)
    return ev


def test_build_merkle_root():
    hashes = [
        "a" * 64,
        "b" * 64,
        "c" * 64,
        "d" * 64,
    ]
    root = build_merkle_root(hashes)
    assert isinstance(root, str)
    assert len(root) == 64

    # Empty leaves returns 64 zeroes
    empty_root = build_merkle_root([])
    assert empty_root == "0" * 64


def test_merkle_audit_chain_and_verify():
    engine = MerkleAuditEngine(
        checkpoint_window_events=5,
        input_csv_hash="input_hash_123",
        region_yaml_hash="yaml_hash_456",
    )

    events = []
    for i in range(12):
        ev = GatewayCrossingEvent(
            event_id=f"EVT_{i:03d}",
            vessel_id="V_CHAIN",
            gateway_id="GATE_A",
            event_type=EventType.ENTRY,
            timestamp=datetime(2024, 3, 15, 12, i, tzinfo=timezone.utc),
            latitude=16.0,
            longitude=65.0,
        )
        chained_ev = engine.ingest_event(ev)
        events.append(chained_ev)

    assert len(engine.chained_events) == 12
    # With window=5, at least 2 checkpoints (at 5 and 10 events) should be generated
    assert len(engine.anchors) >= 2
    assert engine.anchors[0].input_csv_hash == "input_hash_123"
    assert engine.anchors[0].region_yaml_hash == "yaml_hash_456"

    # Verify untampered chain
    result = engine.verify_chain(events)
    assert result.verified is True
    assert result.status == "VERIFY_SUCCESS"
    assert result.total_events == 12


def test_tamper_detection():
    engine = MerkleAuditEngine(checkpoint_window_events=5)
    events = []
    for i in range(8):
        ev = GatewayCrossingEvent(
            event_id=f"EVT_{i:03d}",
            vessel_id="V_TAMPER",
            gateway_id="GATE_A",
            event_type=EventType.ENTRY,
            timestamp=datetime(2024, 3, 15, 12, i, tzinfo=timezone.utc),
            latitude=16.0,
            longitude=65.0,
        )
        events.append(engine.ingest_event(ev))

    # Tamper with event at index 3: modify latitude
    events[3].latitude = 99.999

    tamper_result = engine.verify_chain(events)
    assert tamper_result.verified is False
    assert tamper_result.status == "VERIFY_FAILED"
    assert tamper_result.broken_chain_at == events[3].event_id
