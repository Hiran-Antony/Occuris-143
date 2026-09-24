"""
Unit tests for Module 8 priority state classification.
"""

from src.ais.schemas import InvestigationPriority
from src.ranking.classifier import classify_priority


def test_classify_all_states():
    # (a) One clear high-posterior vessel -> HIGH
    s_high = classify_priority(
        vessel_id="V001",
        all_vessel_posteriors=[0.85, 0.20, 0.10],
        posterior=0.85,
    )
    assert s_high.state == InvestigationPriority.HIGH

    # (b) Two vessels with overlapping intervals -> AMBIGUOUS
    s_amb = classify_priority(
        vessel_id="V001",
        all_vessel_posteriors=[0.72, 0.70, 0.10],
        posterior=0.72,
        intervals={"V001": [0.60, 0.80], "V002": [0.58, 0.78]},
    )
    assert s_amb.state == InvestigationPriority.AMBIGUOUS

    # (c) All posteriors < 0.10 / 0.15 -> NO_STRONG_MATCH
    s_none = classify_priority(
        vessel_id="V001",
        all_vessel_posteriors=[0.08, 0.05, 0.02],
        posterior=0.08,
    )
    assert s_none.state == InvestigationPriority.NO_STRONG_MATCH

    # (d) Posterior 0.50 -> MEDIUM
    s_med = classify_priority(
        vessel_id="V002",
        all_vessel_posteriors=[0.50, 0.20, 0.10],
        posterior=0.50,
    )
    assert s_med.state == InvestigationPriority.MEDIUM

    # (e) Posterior 0.20 -> LOW
    s_low = classify_priority(
        vessel_id="V003",
        all_vessel_posteriors=[0.80, 0.20, 0.10],
        posterior=0.20,
    )
    assert s_low.state == InvestigationPriority.LOW

    # (f) Insufficient data flag -> INSUFFICIENT_DATA
    s_insuf = classify_priority(
        vessel_id="V004",
        all_vessel_posteriors=[],
        is_insufficient_data=True,
    )
    assert s_insuf.state == InvestigationPriority.INSUFFICIENT_DATA
