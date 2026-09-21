"""Integration test suite for full Module 5 pipeline."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.maritime import engine, ensure_pipeline
from src.ais.schemas import (
    AISContinuity,
    BehaviourStatus,
    CollectiveAnomalyType,
)

ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_CSV = ROOT / "data" / "raw" / "synthetic" / "module5_demo.csv"
GROUND_TRUTH_PATH = ROOT / "data" / "raw" / "synthetic" / "ground_truth.json"


@pytest.fixture(scope="module")
def client():
    # Ensure demo pipeline is processed
    engine.load_and_process(DEMO_CSV, seed=42)
    return TestClient(app)


def test_ground_truth_v001(client):
    """V001: Normal Commercial Trader -> NORMAL_TRANSIT, continuous AIS."""
    ass = engine.assessments.get("V001")
    assert ass is not None
    assert ass.status == BehaviourStatus.NORMAL_TRANSIT
    assert ass.ais_continuity == AISContinuity.CONTINUOUS


def test_ground_truth_v002(client):
    """V002: Wind-delayed tanker -> EXPLAINED_DELAY with WEATHER factor."""
    ass = engine.assessments.get("V002")
    assert ass is not None
    assert ass.status == BehaviourStatus.EXPLAINED_DELAY
    weather_factor = next((f for f in ass.explanations if f.factor == "WEATHER"), None)
    assert weather_factor is not None
    assert weather_factor.status.value == "SUPPORTED"


def test_ground_truth_v003(client):
    """V003: Unexplained delay with 38-min blackout -> POTENTIAL_UNEXPLAINED_DELAY."""
    ass = engine.assessments.get("V003")
    assert ass is not None
    assert ass.status == BehaviourStatus.POTENTIAL_UNEXPLAINED_DELAY
    assert ass.ais_continuity == AISContinuity.GAP_DETECTED
    track = engine.tracks.get("V003")
    assert track.gaps[0].duration_minutes >= 35.0


def test_ground_truth_v004_v005_collective(client):
    """V004 + V005: Coordinated dark + rendezvous meeting at sea."""
    collective = engine.collective_events
    dark_events = [e for e in collective if e.anomaly_type == CollectiveAnomalyType.COORDINATED_DARK]
    rdvz_events = [e for e in collective if e.anomaly_type == CollectiveAnomalyType.RENDEZVOUS]

    assert len(dark_events) >= 1
    assert len(rdvz_events) >= 1
    assert "V004" in dark_events[0].vessel_cluster
    assert "V005" in dark_events[0].vessel_cluster
    assert "V004" in rdvz_events[0].vessel_cluster
    assert "V005" in rdvz_events[0].vessel_cluster


def test_api_v1_endpoints(client):
    """Verify all /api/v1 endpoints return 200 with compliant JSON."""
    r_gw = client.get("/api/v1/gateways")
    assert r_gw.status_code == 200
    assert "geojson" in r_gw.json()

    r_vessels = client.get("/api/v1/maritime/vessels")
    assert r_vessels.status_code == 200
    assert len(r_vessels.json()["vessels"]) >= 5

    r_events = client.get("/api/v1/maritime/gateway-events")
    assert r_events.status_code == 200
    assert len(r_events.json()["events"]) >= 4

    r_dna = client.get("/api/v1/maritime/vessels/V001/dna")
    assert r_dna.status_code == 200
    assert "feature_vector" in r_dna.json()["dna"]

    r_anom = client.get("/api/v1/maritime/collective-anomalies")
    assert r_anom.status_code == 200
    assert len(r_anom.json()["events"]) >= 1

    r_verify = client.get("/api/v1/maritime/audit/verify")
    assert r_verify.status_code == 200
    assert r_verify.json()["verification"]["verified"] is True
    assert r_verify.json()["verification"]["status"] == "VERIFY_SUCCESS"

    r_bundle = client.get("/api/v1/maritime/evidence-bundle/V001?case_id=CASE_INT_001")
    assert r_bundle.status_code == 200
    eb = r_bundle.json()["evidence_bundle"]
    assert eb["schema_version"] == "1.0.0"
    assert eb["case_id"] == "CASE_INT_001"
    assert eb["vessel_id"] == "V001"
