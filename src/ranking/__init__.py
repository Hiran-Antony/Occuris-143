"""
Occuris Module 8 — Forensic Ranking Engine

Odds-form Bayesian ranking with likelihood ratio breakdown,
sensitivity analysis, hypothesis testing, and inspection planning.

HONESTY DOCTRINE: Investigation Priority != Guilt
"""

from src.ranking.evidence_engine import EvidenceEngine, load_ranking_config
from src.ranking.sensitivity import compute_sensitivity, sensitivity_analysis, to_sensitivity_contributions
from src.ranking.hypotheses import test_hypotheses, to_hypothesis_posteriors
from src.ranking.planner import plan_inspection, plan_inspections, to_inspection_actions
from src.ranking.classifier import classify_priority
from src.ranking.schemas import (
    AisSourceMode,
    AisState,
    AnalystDecisionRequest,
    HypothesisPosterior,
    HypothesisReport,
    HypothesisTestItem,
    InspectionAction,
    InspectionBudget,
    InspectionPlan,
    InspectionSelectedVessel,
    InvestigationPriority,
    LikelihoodRatioBreakdown,
    PriorityState,
    RankingBundleV1,
    SensitivityContribution,
    SensitivityFactorDelta,
    SensitivityReport,
    VesselRankingEvidence,
)

__all__ = [
    "AisSourceMode",
    "AisState",
    "AnalystDecisionRequest",
    "EvidenceEngine",
    "HypothesisPosterior",
    "HypothesisReport",
    "HypothesisTestItem",
    "InspectionAction",
    "InspectionBudget",
    "InspectionPlan",
    "InspectionSelectedVessel",
    "InvestigationPriority",
    "LikelihoodRatioBreakdown",
    "PriorityState",
    "RankingBundleV1",
    "SensitivityContribution",
    "SensitivityFactorDelta",
    "SensitivityReport",
    "VesselRankingEvidence",
    "classify_priority",
    "compute_sensitivity",
    "load_ranking_config",
    "plan_inspection",
    "plan_inspections",
    "sensitivity_analysis",
    "test_hypotheses",
    "to_hypothesis_posteriors",
    "to_inspection_actions",
    "to_sensitivity_contributions",
]
