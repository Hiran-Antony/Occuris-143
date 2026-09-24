"""
Occuris Module 8 — Leave-One-Evidence-Out (LOO) Sensitivity Analysis

Computes posterior probability deltas when each evidence factor is removed (LR set to 1.0).
Identifies which evidence carries the case, produces robustness bounds,
and establishes the posterior uncertainty interval.

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import copy

from src.ais.schemas import LikelihoodRatioBreakdown, SensitivityContribution
from src.ranking.evidence_engine import EvidenceEngine, load_ranking_config
from src.ranking.schemas import SensitivityFactorDelta, SensitivityReport


def compute_sensitivity(
    vessel_id: str,
    case_id: str,
    prior: float,
    factors: List[LikelihoodRatioBreakdown],
    engine: Optional[EvidenceEngine] = None,
    config: Optional[Dict[str, Any]] = None,
) -> SensitivityReport:
    """
    Compute leave-one-out sensitivity analysis for a vessel.

    For each evidence factor:
    1. Temporarily set its likelihood ratio to 1.0 (neutral).
    2. Recompute posterior with all dependency discounting intact.
    3. Delta = baseline_posterior - posterior_without.
    4. Negative delta = factor increases suspicion; positive = factor exonerates.

    Returns SensitivityReport with sorted top contributors and posterior interval.
    """
    engine = engine or EvidenceEngine(config)
    cfg = config or (engine.config if engine else load_ranking_config())
    sens_cfg = cfg.get("sensitivity", {})
    influential_threshold = float(sens_cfg.get("influential_threshold", 0.10))
    top_n = int(sens_cfg.get("top_n_factors", 5))

    # Baseline posterior with all factors
    baseline_posterior = engine.compute_posterior(prior, factors)

    if not factors:
        return SensitivityReport(
            vessel_id=vessel_id,
            case_id=case_id,
            baseline_posterior=baseline_posterior,
            factor_deltas=[],
            top_contributors=[],
            posterior_interval=[baseline_posterior, baseline_posterior],
        )

    factor_deltas: List[SensitivityFactorDelta] = []
    without_posteriors: List[float] = []

    # Compute LOO for each factor
    raw_deltas = []
    for i, factor in enumerate(factors):
        # Create modified factor list with this factor neutralized (LR = 1.0)
        modified_factors = []
        for j, f in enumerate(factors):
            if i == j:
                modified_factors.append(
                    LikelihoodRatioBreakdown(
                        factor_name=f.factor_name,
                        factor_value=f.factor_value,
                        likelihood_ratio=1.0,
                        rationale=f"Neutralized for sensitivity (original: {f.likelihood_ratio:.2f})",
                        source_module=f.source_module,
                    )
                )
            else:
                modified_factors.append(f)

        posterior_without = engine.compute_posterior(prior, modified_factors)
        without_posteriors.append(posterior_without)
        delta = baseline_posterior - posterior_without
        raw_deltas.append((factor.factor_name, posterior_without, delta))

    # Calculate contribution percentages based on absolute deltas
    total_abs_delta = sum(abs(d[2]) for d in raw_deltas)

    for factor_name, post_without, delta in raw_deltas:
        abs_delta = abs(delta)
        contribution_pct = (abs_delta / total_abs_delta * 100.0) if total_abs_delta > 0 else 0.0

        if abs_delta >= influential_threshold:
            influence = "HIGH"
        elif abs_delta >= (influential_threshold * 0.5):
            influence = "MEDIUM"
        else:
            influence = "LOW"

        factor_deltas.append(
            SensitivityFactorDelta(
                factor_name=factor_name,
                posterior_without=round(post_without, 4),
                delta=round(delta, 4),
                contribution_pct=round(contribution_pct, 2),
                influence=influence,
            )
        )

    # Sort contributors by absolute delta descending
    sorted_contributors = sorted(factor_deltas, key=lambda d: abs(d.delta), reverse=True)
    top_contributors = sorted_contributors[:top_n]

    # Compute posterior interval using prior sensitivity multipliers (from config)
    forensic_cfg = cfg.get("forensic", {}).get("prior_sensitivity", {})
    multipliers = forensic_cfg.get("multipliers", [0.5, 2.0])
    p_low = min(max(prior * multipliers[0], 0.001), 0.999)
    p_high = min(max(prior * multipliers[1], 0.001), 0.999)
    post_low = engine.compute_posterior(p_low, factors)
    post_high = engine.compute_posterior(p_high, factors)

    # Also account for LOO variation in the interval
    min_bound = min(without_posteriors + [post_low, baseline_posterior])
    max_bound = max(without_posteriors + [post_high, baseline_posterior])
    posterior_interval = [round(min_bound, 4), round(max_bound, 4)]

    return SensitivityReport(
        vessel_id=vessel_id,
        case_id=case_id,
        baseline_posterior=round(baseline_posterior, 4),
        factor_deltas=factor_deltas,
        top_contributors=top_contributors,
        posterior_interval=posterior_interval,
    )


def sensitivity_analysis(
    vessel_id: str,
    case_id: str,
    prior: float,
    factors: List[LikelihoodRatioBreakdown],
    engine: Optional[EvidenceEngine] = None,
) -> SensitivityReport:
    """Convenience alias for compute_sensitivity."""
    return compute_sensitivity(
        vessel_id=vessel_id,
        case_id=case_id,
        prior=prior,
        factors=factors,
        engine=engine,
    )


def to_sensitivity_contributions(report: SensitivityReport) -> List[SensitivityContribution]:
    """Convert SensitivityReport to schema-compatible SensitivityContribution list."""
    contributions = []
    for d in report.factor_deltas:
        contributions.append(
            SensitivityContribution(
                factor_name=d.factor_name,
                posterior_with_factor=report.baseline_posterior,
                posterior_without_factor=d.posterior_without,
                delta=abs(d.delta),
                influence=d.influence,
            )
        )
    return contributions
