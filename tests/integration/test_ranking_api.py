"""
Integration tests for Module 8 Ranking API endpoints and Merkle ledger extension.
"""

import copy
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.ais.audit import MerkleAuditEngine
from src.ais.schemas import RankingBundleV1
from src.ranking.audit import record_ranking_artifact, verify_ranking_chain
from src.ranking.ranking_pipeline import run_ranking_pipeline


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_get_case_ranking_endpoint(client):
    """GET /api/v1/ranking/case/{case_id} returns valid frozen RankingBundleV1."""
    resp = client.get("/api/v1/ranking/case/case_01")
    assert resp.status_code == 200
    data = resp.json()

    # Validate against frozen RankingBundleV1 schema
    bundle = RankingBundleV1(**data)
    assert bundle.case_id == "case_01"
    assert bundle.schema_version == "1.0.0"
    assert bundle.module8_version == "8.0.0"
    assert len(bundle.hypothesis_posteriors) >= 2
    assert len(bundle.vessels) > 0
    assert len(bundle.inspection_plan) > 0
    assert bundle.ledger_hash is not None
    assert "Investigation Priority — Not Guilt" in bundle.disclaimer


def test_get_vessel_ranking_endpoint(client):
    """GET /api/v1/ranking/vessels/{vessel_id} returns single vessel dossier."""
    resp = client.get("/api/v1/ranking/vessels/V001?case_id=case_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "case_01"
    vessel = data["vessel"]
    assert vessel["vessel_id"] == "V001"
    assert "posterior" in vessel
    assert "lr_breakdown" in vessel
    assert "sensitivity" in vessel


def test_get_review_queue_endpoint(client):
    """GET /api/v1/ranking/review-queue returns vessels ordered by uncertainty desc."""
    resp = client.get("/api/v1/ranking/review-queue?case_id=case_01")
    assert resp.status_code == 200
    data = resp.json()
    queue = data["review_queue"]
    assert len(queue) > 0

    # Assert sorted descending by uncertainty_width
    widths = [item["uncertainty_width"] for item in queue]
    assert widths == sorted(widths, reverse=True)


def test_analyst_decision_endpoint(client):
    """POST /api/v1/ranking/analyst-decision records decision in SQLite table."""
    payload = {
        "vessel_id": "V001",
        "case_id": "case_01",
        "decision": "follow_up",
        "note": "Forensic analyst priority follow-up recommendation",
        "analyst_id": "analyst_alpha",
    }
    resp = client.post("/api/v1/ranking/analyst-decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "STORED"
    assert data["decision"]["decision"] == "follow_up"

    # Invalid decision test
    bad_payload = dict(payload)
    bad_payload["decision"] = "guilty"  # Forbidden verdict language
    bad_resp = client.post("/api/v1/ranking/analyst-decision", json=bad_payload)
    assert bad_resp.status_code == 400


def test_legacy_candidates_endpoint_varies_honestly(client):
    """GET /api/cases/{case_id}/candidates returns computed results varying by case."""
    resp1 = client.get("/api/cases/case_01/candidates")
    resp2 = client.get("/api/cases/case_02/candidates")
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    cand1 = resp1.json()
    cand2 = resp2.json()
    assert len(cand1) > 0
    assert len(cand2) > 0

    # Must contain physical and evidence metrics, not canned strings
    assert "spatial_evidence" in cand1[0]
    assert "temporal_evidence" in cand1[0]
    assert cand1 != cand2


def test_merkle_ledger_extension_and_tamper():
    """Produce ranking, verify chain contains RANKING_ARTIFACT, tamper, verify TAMPERED."""
    bundle = run_ranking_pipeline("case_01", force_refresh=True)
    assert bundle.ledger_hash is not None

    from src.api.maritime import engine
    audit_engine = engine.audit_engine

    # Check that RANKING_ARTIFACT is in chained_events
    ranking_events = [e for e in audit_engine.chained_events if e.get("event_type") == "RANKING_ARTIFACT"]
    assert len(ranking_events) > 0

    # Verify ledger integrity
    verify_result = verify_ranking_chain(audit_engine)
    assert verify_result.verified is True
    assert verify_result.status == "VERIFY_SUCCESS"

    # Tamper test: tamper with one ranking artifact
    target_idx = next(i for i, e in enumerate(audit_engine.chained_events) if e.get("event_type") == "RANKING_ARTIFACT")
    tampered_events = copy.deepcopy(audit_engine.chained_events)
    tampered_events[target_idx]["top_posterior"] = 0.9999  # Mutate field

    tamper_result = audit_engine.verify_ledger(tampered_events)
    assert tamper_result.verified is False
    assert tamper_result.status == "VERIFY_FAILED"
    assert "Tampered" in tamper_result.details or "Broken" in tamper_result.details
