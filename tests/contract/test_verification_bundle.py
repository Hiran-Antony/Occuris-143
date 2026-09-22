"""Contract tests for frozen Module6VerificationBundleV1 schema."""

import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from src.ais.schemas import (
    AisSourceMode,
    AisState,
    AnomalyClassification,
    AnomalyState,
    Module6VerificationBundleV1,
    VerificationStageStatus,
    WindowResolution,
)


def test_verification_bundle_contract_fields():
    """Verify Module6VerificationBundleV1 fields, defaults, and frozen contract specification."""
    bundle = Module6VerificationBundleV1(
        case_id="CASE_CONTRACT_TEST",
        vessel_id="V_CONTRACT",
    )

    assert bundle.schema_version == "1.0.0"
    assert bundle.case_id == "CASE_CONTRACT_TEST"
    assert bundle.vessel_id == "V_CONTRACT"
    assert bundle.module6_version == "6.0.0"
    assert bundle.window is None
    assert bundle.continuity is None
    assert bundle.kinematic is None
    assert bundle.reachability is None
    assert bundle.dark_path is None
    assert bundle.anomaly_classifications == []
    assert bundle.ais_state == AisState.NORMAL
    assert bundle.integrity_score == 0.9
    assert bundle.integrity_interval == [0.7, 0.95]
    assert bundle.integrity_method == "bayesian_odds_lr"
    assert bundle.concealment_pattern_likelihood == 0.0
    assert bundle.concealment_interval == [0.0, 0.0]
    assert bundle.explanation_distribution == {}
    assert bundle.review_priority == 0.0
    assert bundle.source_mode == AisSourceMode.SYNTHETIC_REPLAY
    assert bundle.generated_at is not None


def test_verification_bundle_json_serialization_roundtrip():
    """Verify clean JSON serialization and deserialization without data corruption."""
    window = WindowResolution(
        vessel_id="V_BUNDLE",
        window_start=datetime(2024, 3, 14, 6, 0, tzinfo=timezone.utc),
        window_end=datetime(2024, 3, 15, 6, 0, tzinfo=timezone.utc),
        overlap_minutes=1440.0,
        vessel_present=True,
    )
    anomaly = AnomalyState(
        anomaly_id="ANOM_001",
        anomaly_type="AIS_GAP",
        classification=AnomalyClassification.EXPLAINED,
        cause="WEATHER",
        explanation_distribution={"WEATHER": 0.85, "COVERAGE": 0.15},
        detail="Weather-correlated gap",
    )
    bundle = Module6VerificationBundleV1(
        case_id="CASE_SER_001",
        vessel_id="V_BUNDLE",
        window=window,
        anomaly_classifications=[anomaly],
        ais_state=AisState.NORMAL,
        integrity_score=0.95,
        ledger_hash="beefcafe" * 8,
    )

    raw_json = bundle.model_dump_json()
    data = json.loads(raw_json)

    assert data["schema_version"] == "1.0.0"
    assert data["case_id"] == "CASE_SER_001"
    assert data["vessel_id"] == "V_BUNDLE"
    assert data["window"]["vessel_present"] is True
    assert len(data["anomaly_classifications"]) == 1
    assert data["anomaly_classifications"][0]["classification"] == "EXPLAINED"
    assert data["ledger_hash"] == "beefcafe" * 8

    # Reconstitute from JSON
    reconstituted = Module6VerificationBundleV1.model_validate_json(raw_json)
    assert reconstituted.case_id == "CASE_SER_001"
    assert reconstituted.anomaly_classifications[0].cause == "WEATHER"
    assert reconstituted.ledger_hash == "beefcafe" * 8


def test_verification_bundle_validation_error():
    """Ensure missing required fields raise Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        # Missing required case_id and vessel_id
        Module6VerificationBundleV1()
