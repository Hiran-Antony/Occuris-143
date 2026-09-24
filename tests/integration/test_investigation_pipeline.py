"""
Integration test suite for full Module 8 Pipeline.
Consumes real M1-M7 outputs and validates Evidence Fusion.
"""

import json
from pathlib import Path
import pytest
from datetime import datetime, timezone, timedelta

from src.api.maritime import engine, ensure_pipeline
from src.ais.schemas import EvidenceBundleV1, CaseContextV1
from src.verification.pipeline import VerificationPipeline, load_verification_config
from src.counterfactual.counterfactual_engine import CounterfactualEngine
from src.investigation.evidence_fusion import fuse_evidence
from src.investigation.schemas import EvidenceState, InvestigationReportBundleV1

ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DATA_DIR = ROOT / "data" / "processed"

# We have 3 known test cases
TEST_CASES = ["case_01", "case_02", "case_03"]


@pytest.fixture(scope="module")
def m5_engine():
    """Ensure M5 engine is initialized with real synthetic AIS test data."""
    ensure_pipeline()
    return engine


@pytest.fixture(scope="module")
def verification_pipeline():
    config = load_verification_config()
    return VerificationPipeline(config)


@pytest.fixture(scope="module")
def counterfactual_engine():
    from src.counterfactual.counterfactual_engine import load_counterfactual_config
    test_cfg_path = ROOT / "config" / "test_counterfactual.yaml"
    cfg = load_counterfactual_config(test_cfg_path)
    return CounterfactualEngine(config=cfg)



def _load_json(case_id: str, suffix: str):
    path = PROCESSED_DATA_DIR / f"{case_id}_{suffix}.json"
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)


def _build_case_context(case_id: str) -> CaseContextV1:
    geom = _load_json(case_id, "geometry")
    spillsplit = _load_json(case_id, "spillsplit")
    
    if not geom or not spillsplit:
        return None

    # Determine sar_acquisition_time from geometry metadata or default
    acq_time_iso = geom.get("metadata", {}).get("acquisition_time", "2024-03-15T12:00:00Z")
    t_sar = datetime.fromisoformat(acq_time_iso.replace("Z", "+00:00"))
    if t_sar.tzinfo is None:
        t_sar = t_sar.replace(tzinfo=timezone.utc)

    # Convert geometry center to spill_center
    raw_center = geom.get("geometry", {}).get("centroid_geo", {})
    center = {
        "lat": raw_center.get("lat", raw_center.get("latitude", 14.8)),
        "lon": raw_center.get("lon", raw_center.get("longitude", 53.1))
    }
    
    return CaseContextV1(
        case_id=case_id,
        origin_zones=spillsplit.get("estimated_origin_zones", []),
        release_window_start=t_sar - timedelta(hours=24),
        release_window_end=t_sar,
        sar_acquisition_time=t_sar,
        spill_center=center
    )


def test_investigation_pipeline(m5_engine, verification_pipeline, counterfactual_engine):
    """
    End-to-end integration test: M5 -> M6 -> M7 -> M8.
    Does not mock data. Instead, it tests the true orchestrated outcome.
    """
    
    # 1. Iterate over all defined cases
    # 1. Iterate over all defined cases
    from src.config import CASES
    
    for case_id in TEST_CASES:
        context = _build_case_context(case_id)
        
        m5_bundles = []
        m6_bundles = []
        
        # 2. Always load M5 bundles (vessels exist regardless of spill)
        for vessel_id, track in m5_engine.tracks.items():
            from src.api.maritime import get_evidence_bundle
            
            bundle_data = get_evidence_bundle(vessel_id, case_id)["evidence_bundle"]
            m5_bundle = EvidenceBundleV1(**bundle_data)
            m5_bundles.append(m5_bundle)
            
            # Run M6 ONLY if context exists
            if context:
                m6_bundle = verification_pipeline.run(m5_bundle, context, track)
                m6_bundles.append(m6_bundle)

        # 3. Run M7 for all vessels in the case
        m7_bundles = []
        if context:
            case_cfg = CASES.get(case_id)
            if case_cfg:
                m7_bundles = counterfactual_engine.run_case(
                    case_id=case_id,
                    case_cfg=case_cfg,
                    m5_bundles=m5_bundles,
                    m6_bundles=m6_bundles,
                    tracks=m5_engine.tracks
                )

        # 4. Fuse evidence (Module 8)
        # We must provide some case config even if context is missing
        case_cfg = CASES.get(case_id) or {
            "id": case_id,
            "sar_timestamp": "2024-03-15T12:00:00Z",
            "release_window_hours": 24,
            "spill_center": {},
            "sar_dataset": {"id": f"SAR_TEST_{case_id}"},
            "ais_dataset": {"id": m5_engine.source.source_mode},
            "environment_dataset": {"id": "TEST_ENV"}
        }

        report = fuse_evidence(
            case_cfg=case_cfg,
            run_id=f"run_{case_id}",
            m5_bundles=m5_bundles,
            m6_bundles=m6_bundles,
            m7_bundles=m7_bundles
        )

        # 5. Verify M8 outputs comply with constraints
        assert isinstance(report, InvestigationReportBundleV1)
        assert len(report.candidate_vessels) == len(m5_engine.tracks)
        
        # If context was missing, ALL candidates must be INSUFFICIENT_DATA
        if not context:
            for candidate in report.candidate_vessels:
                assert candidate.status == EvidenceState.INSUFFICIENT_DATA
            continue
        
        # Make sure no "guilt" related language in the serialized output
        import dataclasses
        report_dict = dataclasses.asdict(report) if dataclasses.is_dataclass(report) else (report.model_dump() if hasattr(report, "model_dump") else report.dict())
        report_json = json.dumps(report_dict, default=str)
        assert "culprit" not in report_json.lower()
        assert "guilty" not in report_json.lower()
        
        # Verify valid evidence states
        valid_states = {s.value for s in EvidenceState}
        for candidate in report.candidate_vessels:
            assert candidate.status.value in valid_states
            assert candidate.vessel_id in m5_engine.tracks
            
            # Ensure provenance is strictly preserved
            assert report.data_provenance.is_synthetic is True
            assert "MVP / SYNTHETIC TEST DATA" in report.data_provenance.synthetic_disclaimer
