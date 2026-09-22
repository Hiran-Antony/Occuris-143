"""
Tests — Module 8 Fusion Logic
"""

import pytest

from src.investigation.candidate_evidence import assemble_candidate_evidence
from src.investigation.schemas import (
    AISEvidence,
    EvidenceState,
    PhysicalEvidence,
    SpatialEvidence,
    TemporalEvidence,
    TemporalOverlap,
)


def _mock_spatial(dist=10.0, intersects=True):
    return SpatialEvidence(
        minimum_distance_to_origin_zone_km=dist,
        time_of_closest_approach_iso="2026-09-04T12:00:00Z",
        intersects_origin_zone=intersects
    )

def _mock_temporal(overlap=TemporalOverlap.TEMPORAL_OVERLAP):
    return TemporalEvidence(
        overlap_status=overlap,
        release_window_start_iso="2026-09-04T08:00:00Z",
        release_window_end_iso="2026-09-04T14:00:00Z",
        vessel_presence_start_iso="2026-09-04T10:00:00Z",
        vessel_presence_end_iso="2026-09-04T12:00:00Z",
        overlap_minutes=120.0
    )

def _mock_ais():
    return AISEvidence(
        ais_status="NORMAL",
        dark_path_hypotheses_evaluated=0,
        data_quality_flags=[]
    )

def _mock_physical(iou=0.8, exceeds_p95=True):
    return PhysicalEvidence(
        hypothesis_id="CF-V123",
        release_time_iso="2026-09-04T11:00:00Z",
        release_location_lat=12.5,
        release_location_lon=64.0,
        release_source="AIS_OBSERVED",
        iou=iou,
        centroid_distance_km=5.0,
        area_similarity=0.9,
        shape_similarity=0.8,
        orientation_similarity=0.95,
        candidate_exceeds_baseline_p95=exceeds_p95,
        time_sensitivity_best_offset_hours=0.0
    )


class TestEvidenceAssembly:
    def test_ideal_supported(self):
        cand = assemble_candidate_evidence(
            "V123", _mock_spatial(), _mock_temporal(), _mock_ais(), _mock_physical()
        )
        assert cand.status == EvidenceState.SUPPORTED
        assert len(cand.contradicting_evidence) == 0

    def test_temporal_contradiction(self):
        cand = assemble_candidate_evidence(
            "V123", _mock_spatial(), _mock_temporal(TemporalOverlap.NO_TEMPORAL_OVERLAP), _mock_ais(), _mock_physical()
        )
        assert cand.status == EvidenceState.CONTRADICTED
        assert any(c.category == "TEMPORAL" for c in cand.contradicting_evidence)

    def test_spatial_contradiction(self):
        cand = assemble_candidate_evidence(
            "V123", _mock_spatial(dist=100.0, intersects=False), _mock_temporal(), _mock_ais(), _mock_physical()
        )
        assert cand.status == EvidenceState.CONTRADICTED
        assert any(c.category == "SPATIAL" for c in cand.contradicting_evidence)

    def test_physical_contradiction(self):
        cand = assemble_candidate_evidence(
            "V123", _mock_spatial(), _mock_temporal(), _mock_ais(), _mock_physical(iou=0.01, exceeds_p95=False)
        )
        assert cand.status == EvidenceState.CONTRADICTED
        assert any(c.category == "PHYSICAL" for c in cand.contradicting_evidence)

    def test_insufficient_data(self):
        cand = assemble_candidate_evidence(
            "V123", _mock_spatial(), _mock_temporal(), _mock_ais(), None
        )
        assert cand.status == EvidenceState.INSUFFICIENT_DATA
