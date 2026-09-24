"""
Occuris Module 8 — Priority State Classification

Assigns forensic investigation priority states to candidate vessels:
  - HIGH: Strong converging evidence; prioritize for tactical inspection
  - MEDIUM: Moderate evidence; secondary inspection tier
  - LOW: Weak or exonerating evidence
  - AMBIGUOUS: Top candidate intervals overlap; differentiation requires more sensing
  - NO_STRONG_MATCH: All candidates fall below minimum suspicion floor
  - INSUFFICIENT_DATA: Critical evidence bundles absent; cannot form evaluation

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from src.ais.schemas import InvestigationPriority
from src.ranking.evidence_engine import load_ranking_config
from src.ranking.schemas import PriorityState


def classify_priority(
    vessel_id: str,
    all_vessel_posteriors: Union[List[float], Dict[str, float]],
    posterior: Optional[float] = None,
    intervals: Optional[Dict[str, List[float]]] = None,
    current_interval: Optional[List[float]] = None,
    is_insufficient_data: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> PriorityState:
    """
    Classify a vessel into one of 6 frozen investigation priority states.

    vessel_id: Candidate vessel identifier.
    all_vessel_posteriors: List or dict of posteriors for all candidates in the case.
    posterior: Posterior for vessel_id (if not in dict or if list passed).
    intervals: Map of vessel_id -> [lower_bound, upper_bound].
    current_interval: [lower, upper] for vessel_id.
    is_insufficient_data: Flag if data was insufficient for evaluation.
    """
    if is_insufficient_data:
        return PriorityState(
            vessel_id=vessel_id,
            state=InvestigationPriority.INSUFFICIENT_DATA,
            reason="Insufficient evidence bundles or sensor data to evaluate candidate.",
        )

    cfg = config or load_ranking_config()
    thresh = cfg.get("thresholds", {})
    high_thresh = float(thresh.get("high_priority", {}).get("lower_bound", 0.70))
    med_thresh = float(thresh.get("medium_priority", {}).get("lower_bound", 0.40))
    min_thresh = float(thresh.get("no_strong_match", {}).get("upper_bound", 0.15))
    overlap_tol = float(thresh.get("ambiguous", {}).get("interval_overlap_tolerance", 0.05))

    # Parse posteriors list
    if isinstance(all_vessel_posteriors, dict):
        post_map = all_vessel_posteriors
        if posterior is None:
            posterior = post_map.get(vessel_id, 0.10)
        post_list = list(post_map.values())
    else:
        post_list = list(all_vessel_posteriors)
        if posterior is None:
            posterior = post_list[0] if post_list else 0.10

    # 1. NO_STRONG_MATCH: All candidates fall below minimum threshold
    if not post_list or max(post_list) < min_thresh:
        return PriorityState(
            vessel_id=vessel_id,
            state=InvestigationPriority.NO_STRONG_MATCH,
            reason=f"All candidates have posterior < {min_thresh:.2f}; no plausible match identified.",
        )

    # Sort all candidates to find top-2
    sorted_posts = sorted(post_list, reverse=True)
    top1 = sorted_posts[0]
    top2 = sorted_posts[1] if len(sorted_posts) > 1 else 0.0

    # 2. Check for AMBIGUITY between top-2 candidates
    # Ambiguous if BOTH top candidates are above medium threshold (or close to each other)
    # AND their intervals overlap significantly
    is_ambiguous = False
    if len(sorted_posts) >= 2:
        # Both top candidates must be credible contenders (top2 >= med_thresh or within tolerance of top1)
        if top1 >= med_thresh and (top2 >= med_thresh or abs(top1 - top2) <= overlap_tol):
            if intervals and len(intervals) >= 2:
                v_sorted = sorted(intervals.keys(), key=lambda v: post_map.get(v, 0.0) if isinstance(all_vessel_posteriors, dict) else 0.0, reverse=True)
                iv1 = intervals[v_sorted[0]]
                iv2 = intervals[v_sorted[1]]
                overlap_len = min(iv1[1], iv2[1]) - max(iv1[0], iv2[0])
                if overlap_len >= overlap_tol or abs(top1 - top2) <= overlap_tol:
                    is_ambiguous = True
            elif abs(top1 - top2) <= overlap_tol:
                is_ambiguous = True

    if is_ambiguous:
        # Only candidates within the contention band get AMBIGUOUS
        if posterior >= med_thresh and (abs(posterior - top1) <= overlap_tol or posterior >= top2 - 1e-6):
            return PriorityState(
                vessel_id=vessel_id,
                state=InvestigationPriority.AMBIGUOUS,
                reason=f"Top candidate posteriors/intervals overlap (top1={top1:.2f}, top2={top2:.2f}); cannot resolve primary target without further observation.",
            )

    # 3. HIGH Priority
    if posterior >= high_thresh:
        return PriorityState(
            vessel_id=vessel_id,
            state=InvestigationPriority.HIGH,
            reason=f"Posterior {posterior:.2f} >= high threshold ({high_thresh:.2f}); strong physical and behavioral consistency.",
        )

    # 4. MEDIUM Priority
    if posterior >= med_thresh:
        return PriorityState(
            vessel_id=vessel_id,
            state=InvestigationPriority.MEDIUM,
            reason=f"Posterior {posterior:.2f} in medium range [{med_thresh:.2f}, {high_thresh:.2f}); moderate consistency.",
        )

    # 5. LOW Priority
    return PriorityState(
        vessel_id=vessel_id,
        state=InvestigationPriority.LOW,
        reason=f"Posterior {posterior:.2f} < medium threshold ({med_thresh:.2f}); weak or exonerating evidence.",
    )
