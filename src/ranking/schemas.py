"""
Occuris Module 8 — Ranking Schemas and Frozen Contracts

Defines all data contracts for Bayesian forensic evidence ranking,
leave-one-out sensitivity analysis, multi-source hypothesis testing,
and decision-optimal inspection planning.

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.ais.schemas import (
    AisSourceMode,
    AisState,
    HypothesisPosterior,
    InspectionAction,
    InvestigationPriority,
    LikelihoodRatioBreakdown,
    RankingBundleV1,
    SensitivityContribution,
    VesselRankingEvidence,
)


class SensitivityFactorDelta(BaseModel):
    """Posterior delta when a specific factor is removed."""
    factor_name: str
    posterior_without: float
    delta: float
    contribution_pct: float
    influence: str = "LOW"  # HIGH | MEDIUM | LOW


class SensitivityReport(BaseModel):
    """Leave-one-evidence-out sensitivity report for a vessel."""
    vessel_id: str
    case_id: str
    baseline_posterior: float
    factor_deltas: List[SensitivityFactorDelta]
    top_contributors: List[SensitivityFactorDelta]
    posterior_interval: List[float] = Field(default_factory=lambda: [0.0, 1.0])


class HypothesisTestItem(BaseModel):
    """Individual hypothesis result."""
    id: str  # H1, H2, H3, H4, H5
    description: str
    posterior: float
    log_likelihood: float
    penalty: float
    status: str  # TESTABLE | INSUFFICIENT_DATA
    bic_score: Optional[float] = None


class HypothesisReport(BaseModel):
    """Multi-source hypothesis testing evaluation report."""
    case_id: str
    hypotheses: List[HypothesisTestItem]
    preferred_hypothesis_id: str
    explanation: str


class InspectionBudget(BaseModel):
    """Patrol resource budget parameters."""
    available_assets: int = 2
    max_hours_per_asset: float = 8.0
    average_speed_kn: float = 25.0
    base_port_lat: float = 16.0
    base_port_lon: float = 64.0

    @property
    def total_asset_hours(self) -> float:
        return float(self.available_assets * self.max_hours_per_asset)


class InspectionSelectedVessel(BaseModel):
    """Selected vessel within inspection plan."""
    vessel_id: str
    posterior: float
    value: float
    transit_cost: float
    marginal_value: float
    order: int = 1
    action_type: str = "BOARD_INSPECT"


class InspectionPlan(BaseModel):
    """Decision-optimal inspection planning output."""
    case_id: str
    selected_vessels: List[InspectionSelectedVessel]
    total_value: float
    budget_remaining: float
    budget_utilization: float
    next_best_action: str


class PriorityState(BaseModel):
    """Priority state assignment result."""
    vessel_id: str
    state: InvestigationPriority
    reason: str


class AnalystDecisionRequest(BaseModel):
    """Analyst review decision payload."""
    vessel_id: str
    case_id: str
    decision: str  # follow_up | reject_with_reason | ambiguous | insufficient
    note: str = ""
    analyst_id: Optional[str] = "analyst_1"


__all__ = [
    "AisSourceMode",
    "AisState",
    "AnalystDecisionRequest",
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
]
