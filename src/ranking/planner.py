"""
Occuris Module 8 — Decision-Optimal Inspection Planning

Greedy submodular optimization for allocating patrol assets (cutters, aircraft)
under operational endurance and transit constraints.

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from src.ais.schemas import InspectionAction
from src.ranking.evidence_engine import load_ranking_config
from src.ranking.schemas import (
    InspectionBudget,
    InspectionPlan,
    InspectionSelectedVessel,
)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute Haversine distance in km between two WGS84 points."""
    r = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def plan_inspections(
    case_id: str,
    vessels: List[Dict[str, Any]],
    budget: Optional[InspectionBudget] = None,
    slick_area_volume_proxy: float = 1.0,
    config: Optional[Dict[str, Any]] = None,
) -> InspectionPlan:
    """
    Select decision-optimal subset of vessels to inspect that maximizes expected value
    under patrol asset and endurance budget constraints.

    vessels: list of dicts with:
      - 'vessel_id': str
      - 'posterior': float
      - 'lat': float (current or last observed latitude)
      - 'lon': float (current or last observed longitude)
      - optional 'vessel_type': str
    """
    cfg = config or load_ranking_config()
    plan_cfg = cfg.get("inspection_planning", {})
    patrol_budget_cfg = plan_cfg.get("patrol_budget", {})
    weights_cfg = plan_cfg.get("value_weights", {})

    if budget is None:
        budget = InspectionBudget(
            available_assets=int(patrol_budget_cfg.get("available_assets", 2)),
            max_hours_per_asset=float(patrol_budget_cfg.get("max_hours_per_asset", 8.0)),
            average_speed_kn=float(patrol_budget_cfg.get("average_speed_kn", 25.0)),
            base_port_lat=float(patrol_budget_cfg.get("base_port_lat", 16.0)),
            base_port_lon=float(patrol_budget_cfg.get("base_port_lon", 64.0)),
        )

    speed_kmh = budget.average_speed_kn * 1.852
    total_budget_hours = budget.total_asset_hours
    deterrence_w = float(weights_cfg.get("deterrence_weight", 0.3))
    posterior_w = float(weights_cfg.get("posterior_weight", 1.0))
    slick_vol_w = float(weights_cfg.get("slick_volume_weight", 0.5))

    # Evaluate candidate value and transit cost
    candidates = []
    for v in vessels:
        vid = v["vessel_id"]
        post = float(v.get("posterior", 0.10))
        lat = float(v.get("lat", budget.base_port_lat))
        lon = float(v.get("lon", budget.base_port_lon))

        dist_km = haversine_distance_km(budget.base_port_lat, budget.base_port_lon, lat, lon)
        # Transit time in hours + 1.0 hr on-scene inspection
        transit_hours = (dist_km / speed_kmh) if speed_kmh > 0 else 1.0
        inspection_cost_hours = transit_hours + 1.0

        # Transit cost penalty factor scaled by endurance
        transit_cost_penalty = (transit_hours / max(budget.max_hours_per_asset, 1.0)) * 0.2

        # Value formula: posterior * slick_area_volume_proxy * deterrence_weight - transit_cost
        raw_value = (
            (post * posterior_w)
            * (1.0 + slick_area_volume_proxy * slick_vol_w)
            * (1.0 + deterrence_w)
            - transit_cost_penalty
        )
        val = max(raw_value, 0.0)

        candidates.append({
            "vessel_id": vid,
            "posterior": post,
            "value": round(val, 4),
            "transit_cost": round(inspection_cost_hours, 2),
            "lat": lat,
            "lon": lon,
        })

    # Sort by value descending
    candidates.sort(key=lambda c: c["value"], reverse=True)

    selected: List[InspectionSelectedVessel] = []
    budget_used = 0.0
    total_val = 0.0
    unselected = []

    for idx, c in enumerate(candidates):
        cost = c["transit_cost"]
        if budget_used + cost <= total_budget_hours:
            budget_used += cost
            total_val += c["value"]
            selected.append(
                InspectionSelectedVessel(
                    vessel_id=c["vessel_id"],
                    posterior=c["posterior"],
                    value=c["value"],
                    transit_cost=cost,
                    marginal_value=c["value"],
                    order=len(selected) + 1,
                    action_type="BOARD_INSPECT" if c["posterior"] >= 0.50 else "AERIAL_SURVEY",
                )
            )
        else:
            unselected.append(c)

    budget_remaining = max(total_budget_hours - budget_used, 0.0)
    budget_utilization = (budget_used / total_budget_hours) if total_budget_hours > 0 else 0.0

    # Determine next best action
    if unselected:
        top_unselected = unselected[0]
        if top_unselected["value"] > 0.15:
            next_best_action = f"inspect {top_unselected['vessel_id']}"
        elif top_unselected["value"] > 0.05:
            next_best_action = "expand search"
        else:
            next_best_action = "insufficient evidence"
    else:
        if not selected:
            next_best_action = "insufficient evidence"
        else:
            next_best_action = "all candidates within budget scheduled"

    return InspectionPlan(
        case_id=case_id,
        selected_vessels=selected,
        total_value=round(total_val, 4),
        budget_remaining=round(budget_remaining, 2),
        budget_utilization=round(budget_utilization, 4),
        next_best_action=next_best_action,
    )


def plan_inspection(
    case_id: str,
    vessels: List[Dict[str, Any]],
    budget: Optional[InspectionBudget] = None,
    slick_area_volume_proxy: float = 1.0,
) -> InspectionPlan:
    """Convenience alias for plan_inspections."""
    return plan_inspections(
        case_id=case_id,
        vessels=vessels,
        budget=budget,
        slick_area_volume_proxy=slick_area_volume_proxy,
    )


def to_inspection_actions(plan: InspectionPlan) -> List[InspectionAction]:
    """Convert InspectionPlan to schema-compatible InspectionAction list."""
    actions = []
    for s in plan.selected_vessels:
        actions.append(
            InspectionAction(
                vessel_id=s.vessel_id,
                order=s.order,
                value=s.value,
                cost=s.transit_cost,
                marginal_value=s.marginal_value,
                action_type=s.action_type,
            )
        )
    return actions
