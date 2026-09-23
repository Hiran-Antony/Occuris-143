"""
Module 8 — Spatial Evidence Analysis

Evaluates proximity to the estimated source zone.
"""

from typing import Optional

from src.ais.schemas import Module6VerificationBundleV1
from src.investigation.schemas import SpatialEvidence


def evaluate_spatial_evidence(
    m6_bundle: Optional[Module6VerificationBundleV1]
) -> SpatialEvidence:
    """
    Evaluates whether the vessel was physically near the estimated source zone.
    Extracts proximity data from Module 6 reachability analysis.
    """
    if not m6_bundle or not m6_bundle.reachability:
        return SpatialEvidence(
            minimum_distance_to_origin_zone_km=-1.0,
            time_of_closest_approach_iso=None,
            intersects_origin_zone=False
        )
    
    reach = m6_bundle.reachability
    
    # We define it intersects if it's reachable according to M6
    intersects = reach.overall_verdict == "REACHABLE"
    
    # Calculate a proxy for minimum_distance_km using round_trip_dark_checks
    min_dist = -1.0
    if reach.round_trip_dark_checks:
        dists = [chk.get("d1_km", 9999.0) for chk in reach.round_trip_dark_checks]
        if dists:
            min_dist = min(dists)
            if min_dist == 9999.0:
                min_dist = -1.0
    if intersects and min_dist < 0:
        min_dist = 0.0
    
    return SpatialEvidence(
        minimum_distance_to_origin_zone_km=min_dist,
        time_of_closest_approach_iso=None,
        intersects_origin_zone=intersects
    )
