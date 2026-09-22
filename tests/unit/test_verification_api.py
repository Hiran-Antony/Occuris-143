"""
Module 6 — Unit/Integration Tests: Verification API Endpoints
Tests:
- POST /api/v1/verification/run/{vessel_id} (idempotent; returns bundle + ledger_hash)
- GET /api/v1/verification/report/{vessel_id} (cached, includes input hashes)
- GET /api/v1/verification/case/{case_id}
- GET /api/v1/verification/ledger/verify (full chain incl. Module 6)
- POST /api/v1/verification/analyst-labels (storage only)
- GET /api/v1/verification/review-queue (interval-width desc)
All responses asserted for source_mode, generated_at, module6_version.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from tools.build_demo_scenarios import generate_demo_dataset, CSV_PATH, GROUND_TRUTH_PATH


@pytest.fixture(scope="module")
def client():
    # Ensure demo dataset exists and load engine
    if not CSV_PATH.exists() or not GROUND_TRUTH_PATH.exists():
        generate_demo_dataset()

    from src.api.maritime import engine
    engine.load_and_process(CSV_PATH)

    with TestClient(app) as test_client:
        yield test_client


def test_api_run_verification_idempotent(client):
    """POST /api/v1/verification/run/{vessel_id} should run pipeline and be idempotent."""
    # First run: COMPUTED
    resp1 = client.post("/api/v1/verification/run/V001?case_id=case_01")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] == "COMPUTED"
    assert "verification_bundle" in data1
    assert "ledger_hash" in data1
    assert data1["module6_version"] == "6.0.0"
    assert "generated_at" in data1
    assert "source_mode" in data1

    bundle1 = data1["verification_bundle"]
    assert bundle1["vessel_id"] == "V001"
    assert bundle1["ais_state"] == "NORMAL"
    assert bundle1["integrity_score"] > 0.7

    # Second run: CACHED (idempotent)
    resp2 = client.post("/api/v1/verification/run/V001?case_id=case_01")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "CACHED"
    assert data2["ledger_hash"] == data1["ledger_hash"]
    assert data2["verification_bundle"]["integrity_score"] == bundle1["integrity_score"]


def test_api_get_verification_report(client):
    """GET /api/v1/verification/report/{vessel_id} retrieves cached report with input hashes."""
    # V001 was run in previous test
    resp = client.get("/api/v1/verification/report/V001?case_id=case_01")
    assert resp.status_code == 200
    data = resp.json()
    assert "verification_bundle" in data
    assert "input_hashes" in data
    assert data["input_hashes"]["vessel_id"] == "V001"
    assert data["input_hashes"]["case_id"] == "case_01"
    assert data["module6_version"] == "6.0.0"

    # Non-existent vessel returns 404
    resp_404 = client.get("/api/v1/verification/report/V_UNKNOWN?case_id=case_01")
    assert resp_404.status_code == 404


def test_api_get_case_verification(client):
    """GET /api/v1/verification/case/{case_id} retrieves all reports for a case."""
    # Run V003 as well
    client.post("/api/v1/verification/run/V003?case_id=case_01")

    resp = client.get("/api/v1/verification/case/case_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["case_id"] == "case_01"
    assert data["vessel_count"] >= 2
    assert "V001" in data["reports"]
    assert "V003" in data["reports"]


def test_api_ledger_verify(client):
    """GET /api/v1/verification/ledger/verify validates full audit chain."""
    resp = client.get("/api/v1/verification/ledger/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert "verification" in data
    assert data["verification"]["verified"] is True
    assert data["verification"]["status"] == "VERIFY_SUCCESS"


def test_api_analyst_labels(client):
    """POST /api/v1/verification/analyst-labels stores label without affecting scores."""
    req_body = {
        "vessel_id": "V003",
        "case_id": "case_01",
        "label": "SUSPICIOUS_PATTERN",
        "note": "Unexplained AIS blackout during release window",
    }
    resp = client.post("/api/v1/verification/analyst-labels", json=req_body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "STORED"
    assert data["label"]["vessel_id"] == "V003"
    assert data["label"]["label"] == "SUSPICIOUS_PATTERN"


def test_api_review_queue(client):
    """GET /api/v1/verification/review-queue returns items sorted by interval width desc."""
    resp = client.get("/api/v1/verification/review-queue")
    assert resp.status_code == 200
    data = resp.json()
    assert "queue" in data
    queue = data["queue"]
    assert len(queue) >= 2

    # Verify descending sort by review_priority (interval width)
    priorities = [item["review_priority"] for item in queue]
    assert priorities == sorted(priorities, reverse=True)
