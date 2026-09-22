"""
Module 7 — Candidate Selector

Filters Module 6 output bundles to vessels eligible for counterfactual
simulation.

Eligibility criteria:
    Temporal: The vessel has an AIS or reconstructed position within or
              sufficiently near the Module 4 release window.
    Spatial:  Module 6 provides evidence of a plausible relationship to the
              origin zone (reachability PASS or dark-path intersection).

Design constraint:
    Do NOT be too aggressive. Missing the true vessel is worse than including
    a false candidate. Preserve the selection reason for audit.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.ais.schemas import EvidenceBundleV1, Module6VerificationBundleV1, VesselTrack
from src.counterfactual.schemas import CandidateSelectionRecord

# Temporal tolerance: a vessel whose track ends this many hours before the
# window start (or begins this many hours after window end) is still eligible.
TEMPORAL_TOLERANCE_HOURS = 2.0


def _temporal_eligible(
    bundle: EvidenceBundleV1,
    m6: Module6VerificationBundleV1,
    track: Optional[VesselTrack],
) -> Tuple[bool, str]:
    """Return (eligible, reason_string)."""
    # Module 6 window resolver already computed vessel_present
    if m6.window and m6.window.vessel_present:
        return True, "TRACK_OVERLAPS_RELEASE_WINDOW"

    # If dark-path hypotheses exist, the vessel may be relevant despite a gap
    if m6.dark_path and m6.dark_path.hypotheses_evaluated > 0:
        return True, "DARK_PATH_COVERS_RELEASE_WINDOW"

    # If explicit window overlap is small, check tolerance
    if m6.window and m6.window.overlap_minutes >= -TEMPORAL_TOLERANCE_HOURS * 60:
        return True, "TRACK_NEAR_RELEASE_WINDOW"

    return False, "NO_TEMPORAL_OVERLAP"


def _spatial_eligible(
    m6: Module6VerificationBundleV1,
) -> Tuple[bool, str]:
    """Return (eligible, reason_string)."""
    from src.ais.schemas import ReachabilityVerdict

    if m6.reachability and m6.reachability.overall_verdict == ReachabilityVerdict.REACHABLE:
        return True, "REACHABILITY_PASS"

    if m6.dark_path and m6.dark_path.dark_path_support:
        return True, "DARK_PATH_INTERSECTS_ORIGIN_ZONE"

    # Generous fallback: include if not explicitly ruled out
    if m6.reachability and m6.reachability.overall_verdict != ReachabilityVerdict.UNREACHABLE:
        return True, "REACHABILITY_NOT_RULED_OUT"

    return False, "REACHABILITY_VIOLATED"


def select_candidates(
    m5_bundles: List[EvidenceBundleV1],
    m6_bundles: List[Module6VerificationBundleV1],
    tracks: Optional[Dict[str, VesselTrack]] = None,
) -> List[Tuple[EvidenceBundleV1, Module6VerificationBundleV1, CandidateSelectionRecord]]:
    """Filter vessels to those eligible for counterfactual simulation.

    Returns
    -------
    List of (EvidenceBundleV1, Module6VerificationBundleV1, selection_record)
    tuples. Eligible and ineligible vessels are both recorded.
    """
    m6_map: Dict[str, Module6VerificationBundleV1] = {b.vessel_id: b for b in m6_bundles}
    result = []

    for m5 in m5_bundles:
        vid = m5.vessel_id
        m6 = m6_map.get(vid)
        if m6 is None:
            record = CandidateSelectionRecord(
                vessel_id=vid,
                eligible=False,
                temporal_reason="NO_M6_BUNDLE",
                spatial_reason="NO_M6_BUNDLE",
                exclusion_reason="Module 6 bundle not found for this vessel.",
            )
            result.append((m5, None, record))
            continue

        track = (tracks or {}).get(vid)
        temp_ok, temp_reason = _temporal_eligible(m5, m6, track)
        spat_ok, spat_reason = _spatial_eligible(m6)

        eligible = temp_ok and spat_ok
        exclusion = None if eligible else f"temp={temp_reason}, spatial={spat_reason}"

        record = CandidateSelectionRecord(
            vessel_id=vid,
            eligible=eligible,
            temporal_reason=temp_reason,
            spatial_reason=spat_reason,
            exclusion_reason=exclusion,
        )
        result.append((m5, m6, record))

    return result
