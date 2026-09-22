"""
Module 7 — Evidence Bundle Assembler

Produces the frozen CounterfactualEvidenceBundleV1 from the engine outputs.
All mandatory interpretation strings and limitation disclaimers are generated
here — they are NOT optional and must appear in every bundle.

FORENSIC BOUNDARY:
    The interpretation string describes physical consistency, not guilt.
    The limitations list is mandatory and must appear in every bundle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.counterfactual.schemas import (
    MODULE7_SCHEMA_VERSION,
    BaselineStats,
    BestHypothesisSummary,
    CandidateSelectionRecord,
    CounterfactualEvidenceBundleV1,
    TimeSensitivity,
)

MODULE7_VERSION = "7.0.0"

_LIMITATIONS = [
    "The release is hypothetical — no actual release event is confirmed.",
    "Environmental forcing (wind, current) contains inherent uncertainty.",
    "AIS reconstruction uncertainty applies where release_source is DARK_PATH_RECONSTRUCTED.",
    "Physical consistency does not establish causation, guilt, or intent.",
    "Results are sensitive to the configured transport model and weight choices.",
]


def _build_interpretation(
    vessel_id: str,
    composite_score: float,
    baseline: Optional[BaselineStats],
    exceeds_p95: Optional[bool],
    time_sensitivity: Optional[TimeSensitivity],
) -> str:
    parts = []

    if composite_score >= 0.70:
        strength = "strong"
    elif composite_score >= 0.45:
        strength = "moderate"
    else:
        strength = "weak"

    parts.append(
        f"The best counterfactual hypothesis for vessel {vessel_id} produces a "
        f"{strength} spatial and geometric match (composite score = {composite_score:.3f}) "
        f"under the configured transport model."
    )

    if baseline is not None and exceeds_p95 is not None:
        if exceeds_p95:
            parts.append(
                f"This score exceeds the 95th percentile of {baseline.n_samples} "
                f"generic origin-zone samples (p95 = {baseline.p95_score:.3f}), "
                f"indicating the match is not explained by general proximity to the origin zone."
            )
        else:
            parts.append(
                f"This score does not exceed the 95th percentile of {baseline.n_samples} "
                f"generic origin-zone samples (p95 = {baseline.p95_score:.3f}). "
                f"The match may be explained by general proximity to the origin zone."
            )

    if time_sensitivity is not None:
        best_off = time_sensitivity.best_offset_hours
        if best_off == 0.0:
            parts.append(
                "Time sensitivity analysis confirms that the match peaks at the "
                "estimated release window (offset = 0 h)."
            )
        else:
            parts.append(
                f"Time sensitivity analysis shows the match peaks at offset "
                f"{best_off:+.0f} h relative to the estimated release time. "
                f"This offset should be reviewed in context of the Module 4 release window."
            )

    return " ".join(parts)


def assemble_bundle(
    case_id: str,
    vessel_id: str,
    selection_record: CandidateSelectionRecord,
    hypotheses_tested: int,
    best_hypothesis: Optional[BestHypothesisSummary],
    baseline: Optional[BaselineStats],
    time_sensitivity: Optional[TimeSensitivity],
    environment_version: str,
) -> CounterfactualEvidenceBundleV1:
    """Assemble and return the frozen evidence bundle."""

    exceeds_p95: Optional[bool] = None
    composite_score = 0.0

    if best_hypothesis is not None:
        composite_score = best_hypothesis.physical_metrics.composite_score
        if baseline is not None and baseline.n_samples > 0:
            exceeds_p95 = composite_score > baseline.p95_score

    interpretation = _build_interpretation(
        vessel_id=vessel_id,
        composite_score=composite_score,
        baseline=baseline,
        exceeds_p95=exceeds_p95,
        time_sensitivity=time_sensitivity,
    )

    return CounterfactualEvidenceBundleV1(
        schema_version=MODULE7_SCHEMA_VERSION,
        case_id=case_id,
        vessel_id=vessel_id,
        module7_version=MODULE7_VERSION,
        selection_record=selection_record,
        hypotheses_tested=hypotheses_tested,
        best_hypothesis=best_hypothesis,
        baseline=baseline,
        candidate_exceeds_p95=exceeds_p95,
        time_sensitivity=time_sensitivity,
        interpretation=interpretation,
        limitations=list(_LIMITATIONS),
        environment_version=environment_version,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
