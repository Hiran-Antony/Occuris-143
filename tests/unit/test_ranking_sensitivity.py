"""
Unit tests for Module 8 leave-one-evidence-out sensitivity analysis.
"""

import pytest
from src.ais.schemas import LikelihoodRatioBreakdown
from src.ranking.evidence_engine import EvidenceEngine
from src.ranking.sensitivity import compute_sensitivity, to_sensitivity_contributions


def test_sensitivity_strong_vs_weak_factor():
    """
    Construct a vessel with one strong factor (LR=15.0) and one weak factor (LR=1.2);
    confirm strong factor's removal drops posterior significantly,
    weak factor's removal has minimal effect.
    """
    engine = EvidenceEngine()
    prior = 0.10

    strong_factor = LikelihoodRatioBreakdown(
        factor_name="counterfactual_match",
        factor_value="excellent_match",
        likelihood_ratio=15.0,
        rationale="Strong forward match",
        source_module="M7",
    )
    weak_factor = LikelihoodRatioBreakdown(
        factor_name="temporal_overlap",
        factor_value="partial_overlap",
        likelihood_ratio=1.2,
        rationale="Weak partial temporal overlap",
        source_module="M8",
    )

    factors = [strong_factor, weak_factor]
    report = compute_sensitivity("V001", "case_01", prior, factors, engine=engine)

    assert report.vessel_id == "V001"
    assert report.case_id == "case_01"
    assert report.baseline_posterior > prior

    # Find factor deltas
    deltas = {d.factor_name: d for d in report.factor_deltas}
    assert "counterfactual_match" in deltas
    assert "temporal_overlap" in deltas

    strong_delta = deltas["counterfactual_match"]
    weak_delta = deltas["temporal_overlap"]

    # Strong factor removal should cause a large drop in posterior
    assert abs(strong_delta.delta) > abs(weak_delta.delta)
    assert abs(strong_delta.delta) > 0.20  # Significant effect
    assert abs(weak_delta.delta) < 0.10   # Minimal effect
    assert strong_delta.influence == "HIGH"

    # Top contributor should be the strong factor
    assert report.top_contributors[0].factor_name == "counterfactual_match"

    # Verify interval bounds
    assert report.posterior_interval[0] <= report.baseline_posterior
    assert report.posterior_interval[1] >= report.baseline_posterior

    # Schema conversion check
    contributions = to_sensitivity_contributions(report)
    assert len(contributions) == 2
    assert contributions[0].posterior_with_factor == report.baseline_posterior


def test_sensitivity_empty_factors():
    """Verify behavior when factors list is empty."""
    engine = EvidenceEngine()
    prior = 0.15
    report = compute_sensitivity("V002", "case_02", prior, [], engine=engine)
    assert report.baseline_posterior == pytest.approx(0.15, abs=1e-4)
    assert len(report.factor_deltas) == 0
    assert len(report.top_contributors) == 0
    assert report.posterior_interval == [0.15, 0.15]
