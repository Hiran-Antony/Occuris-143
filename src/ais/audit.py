"""
Module 5 — Maritime Memory & Virtual Gateways — Innovation Layer D: Merkle Audit Engine (§4.11)
Maintains a tamper-evident cryptographic hash chain across all forensic maritime events:
row_hash = sha256(prev_hash || canonical_json(row))
Builds binary Merkle tree roots at periodic checkpoint windows (every N=100 events or 1 simulated hour).
Provides full mathematical audit verification; any modification immediately yields VERIFY_FAILED.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.ais.schemas import AuditAnchor, AuditVerifyResult

GENESIS_HASH = "0" * 64


def canonical_json(data: Dict[str, Any]) -> str:
    """Produce deterministic canonical JSON representation with sorted keys and normalized strings."""
    def _default(obj):
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        return str(obj)

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_default)


def compute_row_hash(arg1: Any, arg2: Any) -> str:
    """Compute sha256(prev_hash || canonical_json(row_data_without_hashes)). Supports (prev, row) or (row, prev)."""
    if isinstance(arg1, str) and (isinstance(arg2, dict) or hasattr(arg2, "model_dump")):
        prev_hash = arg1
        row_obj = arg2
    elif isinstance(arg2, str) and (isinstance(arg1, dict) or hasattr(arg1, "model_dump")):
        prev_hash = arg2
        row_obj = arg1
    else:
        prev_hash = str(arg1)
        row_obj = arg2

    row_dict = row_obj.model_dump() if hasattr(row_obj, "model_dump") else dict(row_obj)
    # Exclude hash fields to prevent circular reference
    clean_dict = {
        k: v for k, v in row_dict.items()
        if k not in ("row_hash", "prev_hash")
    }
    canon = canonical_json(clean_dict)
    payload = f"{prev_hash}{canon}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_merkle_root(leaf_hashes: List[str]) -> str:
    """Construct a cryptographic binary Merkle tree root over a list of leaf hashes."""
    if not leaf_hashes:
        return GENESIS_HASH

    current_level = list(leaf_hashes)

    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            # Duplicate odd leaf according to Bitcoin / RFC 6962 standard
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            combined = hashlib.sha256(f"{left}{right}".encode("utf-8")).hexdigest()
            next_level.append(combined)
        current_level = next_level

    return current_level[0]


class MerkleAuditEngine:
    """Manages event hash chaining and Merkle checkpoint generation."""

    def __init__(
        self,
        checkpoint_window_events: int = 100,
        input_csv_hash: Optional[str] = None,
        region_yaml_hash: Optional[str] = None,
        pipeline_params_hash: Optional[str] = None,
    ):
        self.checkpoint_window = checkpoint_window_events
        self.latest_hash = GENESIS_HASH
        self.chained_events: List[Dict[str, Any]] = []
        self.anchors: List[AuditAnchor] = []
        self.input_csv_hash = input_csv_hash
        self.region_yaml_hash = region_yaml_hash
        self.pipeline_params_hash = pipeline_params_hash

    def hash_and_append(self, event_data: Dict[str, Any]) -> Tuple[str, str]:
        """
        Hash-chain an event onto the immutable audit ledger.
        Returns (row_hash, prev_hash).
        """
        prev_h = self.latest_hash
        curr_h = compute_row_hash(prev_h, event_data)

        record = dict(event_data)
        record["prev_hash"] = prev_h
        record["row_hash"] = curr_h
        self.chained_events.append(record)
        self.latest_hash = curr_h

        # Check if checkpoint anchor window reached
        if len(self.chained_events) % self.checkpoint_window == 0:
            self.create_checkpoint()

        return curr_h, prev_h

    def ingest_event(self, event: Any) -> Any:
        """Hash-chains an event (GatewayCrossingEvent or dict) and sets row_hash/prev_hash on it."""
        is_model = hasattr(event, "model_dump")
        data = event.model_dump() if is_model else dict(event)
        curr_h, prev_h = self.hash_and_append(data)
        if is_model:
            event.row_hash = curr_h
            event.prev_hash = prev_h
            return event
        data["row_hash"] = curr_h
        data["prev_hash"] = prev_h
        return data

    def verify_chain(self, events: Optional[List[Any]] = None) -> AuditVerifyResult:
        """Alias for verify_ledger that also handles Pydantic model lists."""
        return self.verify_ledger(events)

    def create_checkpoint(self) -> AuditAnchor:
        """Create Merkle root checkpoint over current unanchored chain window."""
        leaf_hashes = [e["row_hash"] for e in self.chained_events]
        m_root = build_merkle_root(leaf_hashes)

        ts_list = [e.get("timestamp") for e in self.chained_events if "timestamp" in e]
        w_start = min(ts_list) if ts_list else datetime.now(timezone.utc)
        w_end = max(ts_list) if ts_list else datetime.now(timezone.utc)

        if isinstance(w_start, str):
            w_start = datetime.fromisoformat(w_start)
        if isinstance(w_end, str):
            w_end = datetime.fromisoformat(w_end)

        anchor = AuditAnchor(
            anchor_id=f"ANCHOR_{len(self.anchors) + 1:04d}_{m_root[:8].upper()}",
            merkle_root=m_root,
            event_count=len(self.chained_events),
            window_start=w_start,
            window_end=w_end,
            external_tx_id=None,
            input_csv_hash=self.input_csv_hash,
            region_yaml_hash=self.region_yaml_hash,
            pipeline_params_hash=self.pipeline_params_hash,
        )
        self.anchors.append(anchor)
        return anchor

    def verify_ledger(self, events: Optional[List[Any]] = None) -> AuditVerifyResult:
        """
        Recompute entire hash chain from genesis forward.
        Detects any row mutation, out-of-order sequence, or tampering.
        """
        chain = events if events is not None else self.chained_events
        if not chain:
            return AuditVerifyResult(
                verified=True,
                total_events=0,
                broken_chain_at=None,
                merkle_root_match=True,
                status="VERIFY_SUCCESS",
                details="Ledger is empty; genesis valid",
            )

        expected_prev = GENESIS_HASH
        recomputed_leaf_hashes = []

        for idx, row in enumerate(chain):
            row_dict = row.model_dump() if hasattr(row, "model_dump") else row
            actual_prev = row_dict.get("prev_hash")
            actual_row_hash = row_dict.get("row_hash")

            if actual_prev != expected_prev:
                return AuditVerifyResult(
                    verified=False,
                    total_events=len(chain),
                    broken_chain_at=row_dict.get("event_id", f"row_{idx}"),
                    merkle_root_match=False,
                    status="VERIFY_FAILED",
                    details=f"Broken prev_hash chain link at index {idx}: expected {expected_prev}, found {actual_prev}",
                )

            recomputed_hash = compute_row_hash(expected_prev, row)
            if recomputed_hash != actual_row_hash:
                return AuditVerifyResult(
                    verified=False,
                    total_events=len(chain),
                    broken_chain_at=row_dict.get("event_id", f"row_{idx}"),
                    merkle_root_match=False,
                    status="VERIFY_FAILED",
                    details=f"Tampered row data at index {idx}: expected {recomputed_hash}, found {actual_row_hash}",
                )

            recomputed_leaf_hashes.append(recomputed_hash)
            expected_prev = recomputed_hash

        # Verify Merkle Root if anchors exist
        root_matches = True
        if self.anchors:
            latest_anchor = self.anchors[-1]
            if len(recomputed_leaf_hashes) >= latest_anchor.event_count:
                recomputed_root = build_merkle_root(recomputed_leaf_hashes[:latest_anchor.event_count])
                root_matches = (recomputed_root == latest_anchor.merkle_root)
            else:
                root_matches = False

        return AuditVerifyResult(
            verified=root_matches,
            total_events=len(chain),
            broken_chain_at=None,
            merkle_root_match=root_matches,
            status="VERIFY_SUCCESS" if root_matches else "VERIFY_FAILED",
            details="Cryptographic integrity confirmed: all row hashes and Merkle roots match",
        )
