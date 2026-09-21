"""
Module 6 — Stage 5: Dark-Path Validator
For each bundle dark-path hypothesis: feasibility (implied speed ≤ limit),
probability mass intersecting origin zone within release window.
Per-hypothesis: {valid, intersects, prob, notes} + aggregate dark_path_support.
Preserves disclaimer: "HYPOTHESIS — reconstructed, not observed".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ais.schemas import (
    CaseContextV1,
    DarkPathHypothesis,
    DarkPathValidation,
    DarkPathValidationEntry,
    EvidenceBundleV1,
    VerificationStageStatus,
)


class DarkPathValidator:
    """Stage 5: Validate dark-path hypotheses against origin zone and feasibility."""

    def __init__(self, config: Dict[str, Any]):
        region_cfg = config.get("_region", {})
        self.vessel_max_speeds = region_cfg.get("vessel_class_max_speeds_kn", {"default": 18.0})
        reach_cfg = config.get("reachability", {})
        self.current_boost_kn = float(reach_cfg.get("current_boost_kn", 2.0))
        self.current_assist = bool(reach_cfg.get("current_assist", True))

    def validate(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
    ) -> DarkPathValidation:
        """Validate all dark-path hypotheses in the evidence bundle."""
        vessel_id = bundle.vessel_id
        hypotheses = bundle.dark_path_hypotheses

        if not hypotheses:
            return DarkPathValidation(
                vessel_id=vessel_id,
                hypotheses_evaluated=0,
                entries=[],
                dark_path_support=False,
                status=VerificationStageStatus.SKIPPED,
            )

        max_speed_kn = float(self.vessel_max_speeds.get("default", 18.0))
        limit_kn = max_speed_kn + (self.current_boost_kn if self.current_assist else 0.0)

        entries: List[DarkPathValidationEntry] = []
        any_support = False

        for hyp in hypotheses:
            hyp_entries = self._validate_hypothesis(hyp, limit_kn)
            entries.extend(hyp_entries)

            # Check if any valid feasible path intersects origin
            for entry in hyp_entries:
                if entry.valid and entry.intersects_origin:
                    any_support = True

        status = (
            VerificationStageStatus.FLAGGED if any_support
            else VerificationStageStatus.PASSED
        )

        return DarkPathValidation(
            vessel_id=vessel_id,
            hypotheses_evaluated=len(hypotheses),
            entries=entries,
            dark_path_support=any_support,
            status=status,
        )

    def _validate_hypothesis(
        self, hyp: DarkPathHypothesis, limit_kn: float
    ) -> List[DarkPathValidationEntry]:
        """Validate individual hypothesis paths."""
        entries: List[DarkPathValidationEntry] = []

        for path in hyp.paths:
            is_feasible = path.implied_speed_knots <= limit_kn
            intersects = path.intersects_origin

            notes_parts = []
            if not is_feasible:
                notes_parts.append(
                    f"Implied speed {path.implied_speed_knots:.1f}kn exceeds "
                    f"limit {limit_kn:.1f}kn"
                )
            if intersects:
                notes_parts.append("Path intersects probable origin zone")
            if path.probability > 0.5:
                notes_parts.append(f"Highest probability path ({path.probability:.2f})")

            entries.append(DarkPathValidationEntry(
                hypothesis_id=hyp.hypothesis_id,
                valid=is_feasible,
                intersects_origin=intersects,
                implied_speed_kn=round(path.implied_speed_knots, 2),
                probability=round(path.probability, 4),
                notes="; ".join(notes_parts) if notes_parts else "Within normal parameters",
                disclaimer="HYPOTHESIS — reconstructed, not observed",
            ))

        return entries
