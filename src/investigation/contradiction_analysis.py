"""
Module 8 — Contradiction Analysis

Actively searches for evidence that contradicts the hypothesis that the candidate
vessel released the oil.
"""

from typing import List, Optional

from src.investigation.schemas import (
    AISEvidence,
    ContradictionEvidence,
    PhysicalEvidence,
    SpatialEvidence,
    TemporalEvidence,
    TemporalOverlap,
)


def find_contradictions(
    spatial: SpatialEvidence,
    temporal: TemporalEvidence,
    ais: AISEvidence,
    physical: Optional[PhysicalEvidence],
) -> List[ContradictionEvidence]:
    """
    Evaluates evidence dimensions against each other to find impossible or
    highly improbable scenarios.
    """
    contradictions = []

    # 1. Temporal exclusion
    if temporal.overlap_status == TemporalOverlap.NO_TEMPORAL_OVERLAP:
        contradictions.append(
            ContradictionEvidence(
                category="TEMPORAL",
                description="The vessel was not present during the estimated release window."
            )
        )

    # 2. Spatial exclusion (assuming large distance)
    # If the minimum distance is > 50km and it never intersected, it's highly unlikely.
    if not spatial.intersects_origin_zone and spatial.minimum_distance_to_origin_zone_km > 50.0:
        contradictions.append(
            ContradictionEvidence(
                category="SPATIAL",
                description=(
                    f"The vessel's closest approach to the origin zone was "
                    f"{spatial.minimum_distance_to_origin_zone_km:.1f} km, which is too far."
                )
            )
        )

    # 3. Physical inconsistency
    if physical is not None:
        if physical.iou < 0.05 and physical.candidate_exceeds_baseline_p95 is False:
            contradictions.append(
                ContradictionEvidence(
                    category="PHYSICAL",
                    description="The counterfactual release fails to reproduce the observed spill and scores below the baseline."
                )
            )

    return contradictions
