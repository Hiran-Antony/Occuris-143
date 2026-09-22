"""
Tests — Module 8 Property Boundaries
"""

import dataclasses
import pytest

from src.investigation.schemas import InvestigationReportBundleV1, EvidenceState
from src.investigation.investigation_report import generate_report_text
from src.investigation.real_data_validator import validate_ais_integrity
from src.ais.schemas import EvidenceBundleV1


class TestBoundaryGuiltLanguage:
    def test_no_guilt_language_in_schemas(self):
        fields = {f.name for f in dataclasses.fields(InvestigationReportBundleV1)}
        forbidden = {"culprit", "guilty", "guilt_probability", "caused_by"}
        assert not fields.intersection(forbidden)

    def test_no_guilt_language_in_report(self):
        # We'll construct a mock bundle and check its report text
        from src.investigation.schemas import DataProvenance
        bundle = InvestigationReportBundleV1(
            schema_version="1.0",
            incident_id="test",
            run_id="run1",
            sar_observation={},
            source_zone={},
            release_window={},
            candidate_vessels=[],
            data_provenance=DataProvenance(
                sar_dataset={}, ais_dataset={}, environment_dataset={},
                is_synthetic=True, synthetic_disclaimer="Test"
            ),
            audit_ledger_reference="urn:test",
            limitations=[],
            generated_at="2026-09-04T12:00:00Z"
        )
        report = generate_report_text(bundle)
        report_lower = report.lower()
        forbidden = ["culprit", "guilty", "guilt probability", "caused by"]
        for f in forbidden:
            assert f not in report_lower

class TestBoundaryRealDataValidator:
    def test_validator_rejects_unmarked_reconstructed_data(self):
        from src.ais.schemas import EvidenceBundleV1, DarkPathHypothesis
        from datetime import datetime
        
        # This dark path hypothesis is maliciously marked as NOT reconstructed
        # (which shouldn't happen, but M8 acts as a firewall)
        bad_hyp = DarkPathHypothesis(
            hypothesis_id="H1",
            vessel_id="V1",
            gap_start=datetime(2026, 9, 4, 12, 0, 0),
            gap_end=datetime(2026, 9, 4, 13, 0, 0),
            start_lat=0.0,
            start_lon=0.0,
            end_lat=0.0,
            end_lon=0.0,
            paths=[],
            disclaimer="Fake observed data" # Malicious!
        )
        
        bundle = EvidenceBundleV1(
            case_id="case1",
            vessel_id="V1",
            dark_path_hypotheses=[bad_hyp]
        )
        
        with pytest.raises(ValueError, match="not marked as reconstructed"):
            validate_ais_integrity(bundle)
