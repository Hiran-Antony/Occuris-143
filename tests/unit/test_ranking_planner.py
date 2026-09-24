"""
Unit tests for Module 8 decision-optimal inspection planning.
"""

from src.ranking.planner import plan_inspections, to_inspection_actions
from src.ranking.schemas import InspectionBudget


def test_inspection_planning_greedy_selection():
    """
    Construct 5 vessels with known posteriors + distances;
    confirm greedy selection matches hand-computed optimal subset
    for a 2-asset, 6-hour budget (total 12 hours).
    """
    budget = InspectionBudget(
        available_assets=2,
        max_hours_per_asset=6.0,
        average_speed_kn=25.0,  # ~46.3 km/h
        base_port_lat=14.5,
        base_port_lon=53.0,
    )

    vessels = [
        {"vessel_id": "V001", "posterior": 0.85, "lat": 14.6, "lon": 53.1},  # Close, very high posterior -> top value
        {"vessel_id": "V002", "posterior": 0.70, "lat": 14.8, "lon": 53.3},  # Close, high posterior -> 2nd value
        {"vessel_id": "V003", "posterior": 0.50, "lat": 15.0, "lon": 53.5},  # Medium distance & posterior
        {"vessel_id": "V004", "posterior": 0.20, "lat": 14.7, "lon": 53.2},  # Low posterior
        {"vessel_id": "V005", "posterior": 0.10, "lat": 18.0, "lon": 58.0},  # Very far, low posterior
    ]

    plan = plan_inspections("case_01", vessels, budget=budget, slick_area_volume_proxy=1.2)

    assert plan.case_id == "case_01"
    assert len(plan.selected_vessels) >= 2
    # First selected vessel should be V001
    assert plan.selected_vessels[0].vessel_id == "V001"
    assert plan.selected_vessels[1].vessel_id == "V002"

    # Budget checks
    total_cost = sum(s.transit_cost for s in plan.selected_vessels)
    assert total_cost <= budget.total_asset_hours
    assert plan.budget_remaining >= 0.0
    assert 0.0 <= plan.budget_utilization <= 1.0

    # Ensure actions are generated
    actions = to_inspection_actions(plan)
    assert len(actions) == len(plan.selected_vessels)
    assert actions[0].order == 1


def test_inspection_planning_exhausted_budget():
    """Test budget constraint when budget is very small."""
    tiny_budget = InspectionBudget(
        available_assets=1,
        max_hours_per_asset=1.5,
        average_speed_kn=25.0,
        base_port_lat=14.5,
        base_port_lon=53.0,
    )
    vessels = [
        {"vessel_id": "V_FAR", "posterior": 0.90, "lat": 25.0, "lon": 65.0},  # ~1500 km away -> ~32 hrs
    ]
    plan = plan_inspections("case_tight", vessels, budget=tiny_budget)
    assert len(plan.selected_vessels) == 0
    assert plan.budget_remaining == 1.5
    assert "inspect" in plan.next_best_action or "search" in plan.next_best_action or "insufficient" in plan.next_best_action
