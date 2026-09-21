"""Contract tests for frozen EvidenceBundleV1 schema."""

import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from src.ais.schemas import (
    AisSourceMode,
    EvidenceBundleV1,
    JourneyStatus,
    ExpectedTimeBasis,
    VesselJourney,
)


def test_evidence_bundle_contract_fields():
    """Verify EvidenceBundleV1 fields, defaults, and frozen contract specification."""
    bundle = EvidenceBundleV1(
        case_id="CASE_CONTRACT_TEST",
        vessel_id="V_CONTRACT",
    )

    assert bundle.schema_version == "1.0.0"
    assert bundle.case_id == "CASE_CONTRACT_TEST"
    assert bundle.vessel_id == "V_CONTRACT"
    assert bundle.journey is None
    assert bundle.ais_gaps == []
    assert bundle.transit_analysis is None
    assert bundle.behaviour_assessment is None
    assert bundle.collective_anomaly_ids == []
    assert bundle.dark_path_hypotheses == []
    assert bundle.source_mode == AisSourceMode.SYNTHETIC_REPLAY
    assert bundle.module5_version == "5.1.0"


def test_evidence_bundle_json_serialization_roundtrip():
    """Verify clean JSON serialization and deserialization without data corruption."""
    journey = VesselJourney(
        journey_id="JRN_001",
        vessel_id="V_BUNDLE",
        distance_km=150.0,
        actual_duration_h=8.0,
        expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
        status=JourneyStatus.COMPLETED,
    )
    bundle = EvidenceBundleV1(
        case_id="CASE_SER_001",
        vessel_id="V_BUNDLE",
        journey=journey,
        latest_event_hash="deadbeef" * 8,
    )

    raw_json = bundle.model_dump_json()
    data = json.loads(raw_json)

    assert data["schema_version"] == "1.0.0"
    assert data["journey"]["journey_id"] == "JRN_001"
    assert data["latest_event_hash"] == "deadbeef" * 8

    # Reconstitute from JSON
    reconstituted = EvidenceBundleV1.model_validate_json(raw_json)
    assert reconstituted.case_id == "CASE_SER_001"
    assert reconstituted.journey.journey_id == "JRN_001"
    assert reconstituted.latest_event_hash == "deadbeef" * 8


def test_evidence_bundle_validation_error():
    """Ensure missing required fields raise Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        # Missing required case_id and vessel_id
        EvidenceBundleV1()
