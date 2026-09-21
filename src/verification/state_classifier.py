"""
Module 6 — Stage 6: State Classifier
(i) Explanation competition: softmax over {COVERAGE, WEATHER, TRAFFIC, OPERATIONAL,
    CONCEALMENT_PATTERN} from documented evidence weights. Per anomaly: EXPLAINED
    (top innocent hypothesis supported) with cause | UNEXPLAINED | INSUFFICIENT_DATA.
    Docstring: "evidential competition, not causal identification".
(ii) Integrity: odds-form Bayes posterior_odds = prior_odds × Π LRᵢ with dependency
     discounting. integrity_interval across prior_sensitivity_range.
(iii) Concealment likelihood: separate odds-form posterior over concealment-informative factors.
(iv) ais_state decision rules; AMBIGUOUS when integrity_interval straddles 0.5 or
     top-two explanations within tolerance.
     review_priority = interval width.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from src.ais.schemas import (
    AisState,
    AnomalyClassification,
    AnomalyState,
    CaseContextV1,
    ContinuityReport,
    DarkPathValidation,
    EvidenceBundleV1,
    KinematicReport,
    Module6VerificationBundleV1,
    ReachabilityResult,
    ReachabilityVerdict,
    VerificationStageStatus,
    WindowResolution,
)


class StateClassifier:
    """Stage 6: Aggregate all stage results into final anomaly classifications and AIS state.

    This is an *evidential competition*, not causal identification.
    The explanation distribution reflects relative evidence support for each hypothesis,
    not the probability that a specific cause is responsible.
    """

    def __init__(self, config: Dict[str, Any]):
        self.explanation_weights = config.get("explanation_weights", {
            "COVERAGE": 1.0,
            "WEATHER": 0.8,
            "TRAFFIC": 0.6,
            "OPERATIONAL": 0.9,
            "CONCEALMENT_PATTERN": 0.7,
        })

        integrity_cfg = config.get("integrity", {})
        self.prior_reliable = float(integrity_cfg.get("prior_reliable", 0.90))
        self.prior_range = integrity_cfg.get("prior_sensitivity_range", [0.70, 0.95])
        self.lr_table = integrity_cfg.get("lr_table", {})
        dep_cfg = integrity_cfg.get("dependency_discount", {})
        self.gap_family_exp = float(dep_cfg.get("gap_family_exponent", 0.7))
        self.ekf_family_exp = float(dep_cfg.get("ekf_family_exponent", 0.7))

    def classify(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
        window: Optional[WindowResolution],
        continuity: Optional[ContinuityReport],
        kinematic: Optional[KinematicReport],
        reachability: Optional[ReachabilityResult],
        dark_path: Optional[DarkPathValidation],
    ) -> Dict[str, Any]:
        """Run explanation competition, integrity scoring, and state classification.

        Returns dict with keys: anomaly_classifications, ais_state, integrity_score,
        integrity_interval, concealment_pattern_likelihood, concealment_interval,
        explanation_distribution, review_priority.
        """
        # (i) Per-anomaly explanation competition
        anomalies = self._classify_anomalies(
            bundle, continuity, kinematic, reachability, dark_path
        )

        # (ii) Integrity scoring
        integrity_score, integrity_interval = self._compute_integrity(
            continuity, kinematic, reachability
        )

        # (iii) Concealment pattern likelihood
        concealment_score, concealment_interval = self._compute_concealment(
            bundle, context, continuity, kinematic, reachability, dark_path, window
        )

        # Global explanation distribution (across all anomalies)
        explanation_dist = self._aggregate_explanation_distribution(anomalies)

        # (iv) AIS state decision
        ais_state = self._decide_ais_state(
            integrity_score, integrity_interval, kinematic, continuity, anomalies
        )

        # Review priority = integrity interval width (wider = more ambiguous)
        review_priority = integrity_interval[1] - integrity_interval[0]

        return {
            "anomaly_classifications": anomalies,
            "ais_state": ais_state,
            "integrity_score": round(integrity_score, 4),
            "integrity_interval": [round(v, 4) for v in integrity_interval],
            "integrity_method": "bayesian_odds_lr",
            "concealment_pattern_likelihood": round(concealment_score, 4),
            "concealment_interval": [round(v, 4) for v in concealment_interval],
            "explanation_distribution": {k: round(v, 4) for k, v in explanation_dist.items()},
            "review_priority": round(review_priority, 4),
        }

    # ── (i) Explanation Competition ───────────────────────────────────────────

    def _classify_anomalies(
        self,
        bundle: EvidenceBundleV1,
        continuity: Optional[ContinuityReport],
        kinematic: Optional[KinematicReport],
        reachability: Optional[ReachabilityResult],
        dark_path: Optional[DarkPathValidation],
    ) -> List[AnomalyState]:
        """Classify each detected anomaly via softmax explanation competition."""
        anomalies: List[AnomalyState] = []

        # AIS Gap anomalies
        if continuity and continuity.total_gaps > 0:
            for gap_rec in continuity.gap_concurrency_records:
                evidence = self._collect_gap_evidence(gap_rec, bundle)
                dist = self._softmax_competition(evidence)
                top_cause = max(dist, key=dist.get)  # type: ignore
                top_value = dist[top_cause]

                # Innocent causes: COVERAGE, WEATHER, TRAFFIC, OPERATIONAL
                innocent_causes = {"COVERAGE", "WEATHER", "TRAFFIC", "OPERATIONAL"}

                if top_cause in innocent_causes and top_value > 0.3:
                    classification = AnomalyClassification.EXPLAINED
                    cause = top_cause
                elif sum(dist.get(c, 0) for c in innocent_causes) < 0.2:
                    classification = AnomalyClassification.UNEXPLAINED
                    cause = None
                else:
                    classification = AnomalyClassification.INSUFFICIENT_DATA
                    cause = None

                anomalies.append(AnomalyState(
                    anomaly_type="AIS_GAP",
                    classification=classification,
                    cause=cause,
                    explanation_distribution=dist,
                    detail=f"Gap {gap_rec.duration_minutes:.0f}min, "
                           f"concurrent_vessels={gap_rec.concurrent_vessel_count}",
                ))

        # Kinematic episode anomalies
        if kinematic and kinematic.episodes:
            for episode in kinematic.episodes:
                anomalies.append(AnomalyState(
                    anomaly_type="KINEMATIC_EPISODE",
                    classification=AnomalyClassification.UNEXPLAINED,
                    cause=None,
                    explanation_distribution={},
                    detail=f"Episode type={episode.episode_type.value}, "
                           f"pings={len(episode.events)}, "
                           f"duration={episode.duration_minutes:.1f}min",
                ))

        # Identity conflict anomalies
        if kinematic and kinematic.identity_conflicts:
            for conflict in kinematic.identity_conflicts:
                anomalies.append(AnomalyState(
                    anomaly_type="IDENTITY_CONFLICT",
                    classification=AnomalyClassification.UNEXPLAINED,
                    cause=None,
                    explanation_distribution={},
                    detail=f"MMSI={conflict.mmsi} at {conflict.separation_km:.1f}km "
                           f"separation within {conflict.dt_minutes:.0f}min "
                           f"— SPOOFING_CANDIDATE evidence tag",
                ))

        return anomalies

    def _collect_gap_evidence(
        self, gap_rec: Any, bundle: EvidenceBundleV1
    ) -> Dict[str, float]:
        """Collect evidence weights for a gap anomaly."""
        evidence: Dict[str, float] = {}

        # COVERAGE: concurrent gaps suggest infrastructure issue
        if gap_rec.coverage_flag:
            evidence["COVERAGE"] = self.explanation_weights.get("COVERAGE", 1.0) * 1.5
        else:
            evidence["COVERAGE"] = self.explanation_weights.get("COVERAGE", 1.0) * 0.2

        # WEATHER: check from behaviour assessment
        weather_support = False
        if bundle.behaviour_assessment:
            for exp in bundle.behaviour_assessment.explanations:
                if exp.factor == "WEATHER" and exp.status.value == "SUPPORTED":
                    weather_support = True
                    break
        evidence["WEATHER"] = (
            self.explanation_weights.get("WEATHER", 0.8) * (1.5 if weather_support else 0.3)
        )

        # TRAFFIC: from behaviour assessment
        traffic_support = False
        if bundle.behaviour_assessment:
            for exp in bundle.behaviour_assessment.explanations:
                if exp.factor == "TRAFFIC" and exp.status.value == "SUPPORTED":
                    traffic_support = True
                    break
        evidence["TRAFFIC"] = (
            self.explanation_weights.get("TRAFFIC", 0.6) * (1.2 if traffic_support else 0.3)
        )

        # OPERATIONAL: from nav status
        nav_support = False
        if bundle.behaviour_assessment:
            for exp in bundle.behaviour_assessment.explanations:
                if exp.factor == "NAV_STATUS" and exp.status.value == "SUPPORTED":
                    nav_support = True
                    break
        evidence["OPERATIONAL"] = (
            self.explanation_weights.get("OPERATIONAL", 0.9) * (1.3 if nav_support else 0.2)
        )

        # CONCEALMENT_PATTERN: solo gap in otherwise covered area
        concealment_score = self.explanation_weights.get("CONCEALMENT_PATTERN", 0.7)
        if not gap_rec.coverage_flag and gap_rec.concurrent_vessel_count == 0:
            concealment_score *= 1.5  # Solo gap amplifies concealment
        else:
            concealment_score *= 0.3  # Concurrent gaps reduce concealment

        evidence["CONCEALMENT_PATTERN"] = concealment_score

        return evidence

    def _softmax_competition(self, evidence: Dict[str, float]) -> Dict[str, float]:
        """Apply softmax to evidence weights to produce explanation distribution."""
        if not evidence:
            return {}

        keys = list(evidence.keys())
        values = np.array([evidence[k] for k in keys])

        # Softmax with temperature scaling
        exp_values = np.exp(values - np.max(values))
        probs = exp_values / np.sum(exp_values)

        return {k: float(p) for k, p in zip(keys, probs)}

    # ── (ii) Integrity Scoring ────────────────────────────────────────────────

    def _compute_integrity(
        self,
        continuity: Optional[ContinuityReport],
        kinematic: Optional[KinematicReport],
        reachability: Optional[ReachabilityResult],
    ) -> tuple:
        """Compute Bayesian odds-form integrity score with dependency discounting."""
        # Collect LR factors by family
        gap_lrs: List[float] = []
        ekf_lrs: List[float] = []
        other_lrs: List[float] = []

        if continuity:
            if continuity.total_gaps == 0 and not (kinematic and (kinematic.episodes or kinematic.identity_conflicts)):
                gap_lrs.append(self._lr("continuous_ais"))
            elif continuity.max_gap_minutes > 60:
                gap_lrs.append(self._lr("gap_long"))
            elif continuity.total_gaps > 0:
                gap_lrs.append(self._lr("gap_short"))

        if kinematic:
            if kinematic.episodes:
                ekf_lrs.append(self._lr("ekf_episode"))
                # Check for speed impossible or teleport jump
                for ep in kinematic.episodes:
                    if any(e.flag.value in ["SPEED_IMPOSSIBLE", "TELEPORT_JUMP"] for e in ep.events):
                        ekf_lrs.append(self._lr("speed_impossible"))
                        break
            else:
                ekf_lrs.append(self._lr("ekf_clean"))

            if kinematic.identity_conflicts:
                other_lrs.append(self._lr("identity_conflict"))

        # Apply dependency discounting within families
        combined_gap_lr = self._discount_combine(gap_lrs, self.gap_family_exp)
        combined_ekf_lr = self._discount_combine(ekf_lrs, self.ekf_family_exp)
        combined_other_lr = math.prod(other_lrs) if other_lrs else 1.0

        # Overall LR product
        total_lr = combined_gap_lr * combined_ekf_lr * combined_other_lr

        # Compute posterior for central prior and bounds
        score = self._odds_to_prob(self._prob_to_odds(self.prior_reliable) * total_lr)
        lo = self._odds_to_prob(self._prob_to_odds(self.prior_range[0]) * total_lr)
        hi = self._odds_to_prob(self._prob_to_odds(self.prior_range[1]) * total_lr)

        return score, [lo, hi]

    def _discount_combine(self, lrs: List[float], exponent: float) -> float:
        """Combine correlated LRs with dependency discounting."""
        if not lrs:
            return 1.0
        if len(lrs) == 1:
            return lrs[0]

        # Sort: strongest evidence first (furthest from 1.0)
        sorted_lrs = sorted(lrs, key=lambda x: abs(math.log(max(x, 1e-10))))
        result = sorted_lrs[0]
        for lr in sorted_lrs[1:]:
            # Discount additional evidence by exponent
            discounted = lr ** exponent
            result *= discounted
        return result

    def _lr(self, factor_name: str) -> float:
        """Look up likelihood ratio from config."""
        entry = self.lr_table.get(factor_name, {})
        if isinstance(entry, dict):
            return float(entry.get("value", 1.0))
        return float(entry)

    @staticmethod
    def _prob_to_odds(p: float) -> float:
        p = max(1e-10, min(1 - 1e-10, p))
        return p / (1 - p)

    @staticmethod
    def _odds_to_prob(odds: float) -> float:
        return odds / (1 + odds)

    # ── (iii) Concealment Pattern Likelihood ──────────────────────────────────

    def _compute_concealment(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
        continuity: Optional[ContinuityReport],
        kinematic: Optional[KinematicReport],
        reachability: Optional[ReachabilityResult],
        dark_path: Optional[DarkPathValidation],
        window: Optional[WindowResolution],
    ) -> tuple:
        """Compute concealment pattern likelihood using concealment-informative factors."""
        # Concealment-informative LRs (inverse perspective: LR > 1 favours concealment)
        concealment_lrs: List[float] = []

        # Solo gap in covered area + window overlap
        if continuity and continuity.total_gaps > 0:
            if not continuity.coverage_support:
                concealment_lrs.append(2.5)  # Solo gap in covered area
            if window and window.vessel_present and window.overlap_minutes > 0:
                concealment_lrs.append(1.8)  # Gap overlaps investigation window

        # Dark path intersects origin
        if dark_path and dark_path.dark_path_support:
            concealment_lrs.append(2.0)  # Feasible path to origin zone

        # Reachability verdict
        if reachability:
            if reachability.overall_verdict == ReachabilityVerdict.REACHABLE:
                concealment_lrs.append(1.3)  # Could have reached origin
            elif reachability.overall_verdict == ReachabilityVerdict.IMPLAUSIBLE:
                concealment_lrs.append(0.3)  # Couldn't have reached origin

        # Kinematic anomalies (evasive course)
        if kinematic and kinematic.episodes:
            concealment_lrs.append(1.5)

        # Base concealment prior: low (0.1)
        concealment_prior = 0.10
        total_lr = math.prod(concealment_lrs) if concealment_lrs else 1.0

        score = self._odds_to_prob(self._prob_to_odds(concealment_prior) * total_lr)
        # Sensitivity bounds
        lo = self._odds_to_prob(self._prob_to_odds(0.05) * total_lr)
        hi = self._odds_to_prob(self._prob_to_odds(0.20) * total_lr)

        return score, [lo, hi]

    # ── (iv) AIS State Decision ───────────────────────────────────────────────

    def _decide_ais_state(
        self,
        integrity_score: float,
        integrity_interval: List[float],
        kinematic: Optional[KinematicReport],
        continuity: Optional[ContinuityReport],
        anomalies: List[AnomalyState],
    ) -> AisState:
        """Decide vessel AIS state from integrity score and evidence."""
        has_identity_conflict = (
            kinematic is not None and len(kinematic.identity_conflicts) > 0
        )
        has_kinematic_episodes = (
            kinematic is not None and len(kinematic.episodes) > 0
        )
        has_gaps = continuity is not None and continuity.total_gaps > 0

        # REPORTING_ANOMALY: identity conflict or teleport jump (hard physical impossibilities)
        has_teleport = (
            kinematic is not None
            and any(
                e.flag.value == "TELEPORT_JUMP"
                for ep in kinematic.episodes
                for e in ep.events
            )
        )
        if has_identity_conflict or has_teleport:
            return AisState.REPORTING_ANOMALY

        # AMBIGUOUS: integrity interval straddles 0.5
        if integrity_interval[0] < 0.5 < integrity_interval[1]:
            return AisState.AMBIGUOUS

        # Check if top-two explanations within tolerance
        for anomaly in anomalies:
            dist = anomaly.explanation_distribution
            if len(dist) >= 2:
                sorted_vals = sorted(dist.values(), reverse=True)
                if sorted_vals[0] - sorted_vals[1] < 0.05:
                    return AisState.AMBIGUOUS

        # REPORTING_ANOMALY: severe kinematic episodes with low integrity
        if has_kinematic_episodes and integrity_score < 0.5:
            return AisState.REPORTING_ANOMALY

        # AIS_GAP_DARK: gaps with low integrity
        if has_gaps and integrity_score < 0.5:
            return AisState.AIS_GAP_DARK

        # AIS_GAP_DARK: gaps present but explained
        if has_gaps and integrity_score >= 0.5:
            # Check if all gap anomalies are explained
            gap_anomalies = [a for a in anomalies if a.anomaly_type == "AIS_GAP"]
            if all(a.classification == AnomalyClassification.EXPLAINED for a in gap_anomalies):
                return AisState.NORMAL
            return AisState.AIS_GAP_DARK

        return AisState.NORMAL

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _aggregate_explanation_distribution(
        self, anomalies: List[AnomalyState]
    ) -> Dict[str, float]:
        """Aggregate explanation distributions across all anomalies."""
        if not anomalies:
            return {}

        totals: Dict[str, float] = {}
        count = 0
        for a in anomalies:
            for k, v in a.explanation_distribution.items():
                totals[k] = totals.get(k, 0.0) + v
                count += 1

        if not totals:
            return {}

        # Normalize
        total_sum = sum(totals.values())
        if total_sum > 0:
            return {k: v / total_sum for k, v in totals.items()}
        return totals
