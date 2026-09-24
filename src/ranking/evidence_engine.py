"""
Occuris Module 8 — Evidence Engine

Odds-form Bayesian ranking with dependency discounting.
Computes posterior P(plausible source | evidence) from Module 5/6/7 bundles.

CRITICAL: Never declares guilt. Output is investigation priority probability.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml
import math

from src.ais.schemas import (
    EvidenceBundleV1,
    Module6VerificationBundleV1,
    AisState,
    LikelihoodRatioBreakdown,
)
from src.counterfactual.schemas import CounterfactualEvidenceBundleV1


def load_ranking_config() -> Dict[str, Any]:
    """Load config/ranking.yaml with all priors, LRs, and thresholds."""
    config_path = Path("config/ranking.yaml")
    if not config_path.exists():
        raise FileNotFoundError(f"config/ranking.yaml not found at {config_path}")
    
    with open(config_path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    
    config: Dict[str, Any] = {}
    for doc in docs:
        if isinstance(doc, dict):
            config.update(doc)
    return config


class EvidenceEngine:
    """
    Odds-form Bayesian evidence evaluator with dependency discounting.
    
    Posterior odds = Prior odds × Π LRᵢ (over independent factors)
    
    Correlated factors grouped and combined via max-LR or geometric mean
    to avoid naive multiplication inflation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_ranking_config()
        
        self.priors = self.config["priors"]
        self.lrs = self.config["likelihood_ratios"]
        self.groups = self.config["dependency_groups"]
    
    def get_prior(
        self, 
        vessel_type: Optional[str] = None,
        is_dark: bool = False
    ) -> float:
        """Get prior probability for vessel."""
        # Base prior by vessel type
        prior = self.priors["vessel_type"].get(
            vessel_type, 
            self.priors["default"]
        )
        
        # Apply dark vessel multiplier if AIS was off during release window
        if is_dark:
            prior *= self.priors["dark_vessel_multiplier"]
        
        # Clamp to [0,1]
        return min(max(prior, 0.0), 1.0)
    
    def compute_lr(
        self,
        factor_name: str,
        factor_value: Any,
        config_key: str,
        rationale: str = ""
    ) -> Tuple[float, str, str]:
        """
        Compute likelihood ratio for a single evidence factor.
        
        Returns: (lr, rationale, source_module)
        """
        lr_config = self.lrs.get(config_key, {})
        
        # Handle different value types
        if isinstance(factor_value, (int, float)):
            # Numeric thresholds (e.g., IoU, distance)
            lr_entry = self._match_numeric_threshold(factor_value, lr_config)
        elif isinstance(factor_value, str):
            # Categorical (e.g., "NORMAL", "AIS_GAP_DARK")
            lr_entry = lr_config.get(factor_value, {})
        elif isinstance(factor_value, bool):
            # Boolean (e.g., intersects_origin)
            key = "intersects" if factor_value else "does_not_intersect"
            lr_entry = lr_config.get(key, {})
        else:
            # Unknown type, default neutral
            return 1.0, "Unknown evidence type; neutral", "M8"
        
        lr = lr_entry.get("lr", 1.0)
        rationale = lr_entry.get("rationale", rationale or "No rationale provided")
        
        return lr, rationale, self._infer_source_module(config_key)
    
    def _match_numeric_threshold(self, value: float, lr_config: Dict) -> Dict:
        """Match numeric value to threshold-based LR config."""
        # For counterfactual IoU + distance
        if "excellent_match" in lr_config:
            # Check in order: excellent > good > weak > poor
            # This is a simplified heuristic; real implementation should check actual thresholds
            if value >= 0.6:
                return lr_config.get("excellent_match", {})
            elif value >= 0.4:
                return lr_config.get("good_match", {})
            elif value >= 0.2:
                return lr_config.get("weak_match", {})
            else:
                return lr_config.get("poor_match", {})
        
        # For AIS integrity score
        if "high_integrity" in lr_config:
            if value >= 0.9:
                return lr_config.get("high_integrity", {})
            elif value >= 0.5:
                return lr_config.get("medium_integrity", {})
            else:
                return lr_config.get("low_integrity", {})
        
        # For distance thresholds
        if "within_10km" in lr_config:
            if value <= 10.0:
                return lr_config.get("within_10km", {})
            elif value <= 30.0:
                return lr_config.get("within_30km", {})
            else:
                return lr_config.get("beyond_30km", {})
        
        # Default neutral
        return {"lr": 1.0, "rationale": "No threshold matched"}
    
    def _infer_source_module(self, config_key: str) -> str:
        """Infer which module produced this evidence."""
        if config_key in ["collective_anomaly", "dark_path_origin_intersection"]:
            return "M5"
        elif config_key in ["ais_state", "ais_integrity_score", "reachability", "explanation"]:
            return "M6"
        elif config_key in ["counterfactual_match"]:
            return "M7"
        elif config_key in ["spillsplit_assignment"]:
            return "M4"
        elif config_key in ["temporal_overlap", "spatial_proximity"]:
            return "M8"
        else:
            return "M8"
    
    def extract_factors(
        self,
        vessel_id: str,
        m5_bundle: EvidenceBundleV1,
        m6_bundle: Optional[Module6VerificationBundleV1],
        m7_bundle: Optional[CounterfactualEvidenceBundleV1],
        case_context: Dict[str, Any]
    ) -> List[LikelihoodRatioBreakdown]:
        """
        Extract all evidence factors from M5/M6/M7 bundles.
        
        Returns list of LikelihoodRatioBreakdown for this vessel.
        """
        factors = []
        
        # ─────────────────────────────────────────────────────────────────────
        # MODULE 7: Counterfactual Match
        # ─────────────────────────────────────────────────────────────────────
        if m7_bundle and m7_bundle.best_hypothesis:
            iou = m7_bundle.best_hypothesis.physical_metrics.iou
            lr, rat, src = self.compute_lr(
                "counterfactual_iou",
                iou,
                "counterfactual_match",
                f"IoU={iou:.2f}"
            )
            factors.append(LikelihoodRatioBreakdown(
                factor_name="counterfactual_match",
                factor_value=f"iou_{iou:.2f}",
                likelihood_ratio=lr,
                rationale=rat,
                source_module=src
            ))
        
        # ─────────────────────────────────────────────────────────────────────
        # TEMPORAL OVERLAP (computed from M6 window or case context)
        # ─────────────────────────────────────────────────────────────────────
        if m6_bundle and m6_bundle.window:
            raw_status = getattr(m6_bundle.window, "overlap_status", None)
            if raw_status:
                overlap_status = str(raw_status).lower()
                if "full" in overlap_status:
                    overlap_status = "full_overlap"
                elif "partial" in overlap_status:
                    overlap_status = "partial_overlap"
                else:
                    overlap_status = "no_overlap"
            else:
                mins = float(getattr(m6_bundle.window, "overlap_minutes", 0.0))
                if mins >= 60.0:
                    overlap_status = "full_overlap"
                elif mins > 0.0 or getattr(m6_bundle.window, "vessel_present", False):
                    overlap_status = "partial_overlap"
                else:
                    overlap_status = "no_overlap"

            lr, rat, src = self.compute_lr(
                "temporal_overlap",
                overlap_status,
                "temporal_overlap",
                f"Overlap: {overlap_status}"
            )
            factors.append(LikelihoodRatioBreakdown(
                factor_name="temporal_overlap",
                factor_value=overlap_status,
                likelihood_ratio=lr,
                rationale=rat,
                source_module=src
            ))
        
        # ─────────────────────────────────────────────────────────────────────
        # SPATIAL PROXIMITY (computed from case_context origin zones)
        # ─────────────────────────────────────────────────────────────────────
        if "min_distance_km" in case_context:
            dist = float(case_context["min_distance_km"])
            spatial_cfg = self.config.get("likelihood_ratios", {}).get("spatial_proximity", {})
            if dist <= 5.0 and "intersects_origin" in spatial_cfg:
                val_key = "intersects_origin"
            elif dist <= 10.0:
                val_key = "within_10km"
            elif dist <= 30.0:
                val_key = "within_30km"
            else:
                val_key = "beyond_30km"
            lr, rat, src = self.compute_lr(
                "spatial_proximity",
                val_key,
                "spatial_proximity",
                f"Distance to origin: {dist:.1f}km ({val_key})"
            )
            factors.append(LikelihoodRatioBreakdown(
                factor_name="spatial_proximity",
                factor_value=val_key,
                likelihood_ratio=lr,
                rationale=rat,
                source_module="M8"
            ))
        
        # ─────────────────────────────────────────────────────────────────────
        # MODULE 6: AIS State
        # ─────────────────────────────────────────────────────────────────────
        if m6_bundle:
            ais_state_str = m6_bundle.ais_state.value
            lr, rat, src = self.compute_lr(
                "ais_state",
                ais_state_str,
                "ais_state",
                f"AIS State: {ais_state_str}"
            )
            factors.append(LikelihoodRatioBreakdown(
                factor_name="ais_state",
                factor_value=ais_state_str,
                likelihood_ratio=lr,
                rationale=rat,
                source_module=src
            ))
            
            # AIS Integrity Score
            integrity = m6_bundle.integrity_score
            lr, rat, src = self.compute_lr(
                "ais_integrity",
                integrity,
                "ais_integrity_score",
                f"Integrity={integrity:.2f}"
            )
            factors.append(LikelihoodRatioBreakdown(
                factor_name="ais_integrity_score",
                factor_value=f"integrity_{integrity:.2f}",
                likelihood_ratio=lr,
                rationale=rat,
                source_module=src
            ))
            
            # Explanation (if available)
            if m6_bundle.explanation_distribution:
                # Find dominant explanation (max probability)
                if m6_bundle.explanation_distribution:
                    dominant = max(
                        m6_bundle.explanation_distribution.items(),
                        key=lambda x: x[1]
                    )[0]
                    
                    lr, rat, src = self.compute_lr(
                        "explanation",
                        dominant,
                        "explanation",
                        f"Dominant explanation: {dominant}"
                    )
                    factors.append(LikelihoodRatioBreakdown(
                        factor_name="explanation",
                        factor_value=dominant,
                        likelihood_ratio=lr,
                        rationale=rat,
                        source_module=src
                    ))
        
        # ─────────────────────────────────────────────────────────────────────
        # MODULE 5: Collective Anomalies
        # ─────────────────────────────────────────────────────────────────────
        collective_anomalies = getattr(m5_bundle, "collective_anomalies", None) or getattr(m5_bundle, "collective_anomaly_ids", [])
        if collective_anomalies:
            anomaly_types_map = case_context.get("anomaly_types", {})
            for anomaly in collective_anomalies:
                anom_type = getattr(anomaly, "anomaly_type", anomaly)
                if hasattr(anom_type, "value"):
                    anom_type = anom_type.value
                anom_type_str = str(anom_type)
                if anom_type_str in anomaly_types_map:
                    anom_type_str = str(anomaly_types_map[anom_type_str])
                anom_key = anom_type_str.lower()
                lr, rat, src = self.compute_lr(
                    "collective_anomaly",
                    anom_key,
                    "collective_anomaly",
                    f"Collective anomaly: {anom_key}"
                )
                factors.append(LikelihoodRatioBreakdown(
                    factor_name="collective_anomaly",
                    factor_value=anom_key,
                    likelihood_ratio=lr,
                    rationale=rat,
                    source_module=src
                ))

        # ─────────────────────────────────────────────────────────────────────
        # MODULE 5: Dark Path Origin Intersection
        # ─────────────────────────────────────────────────────────────────────
        dp_hypotheses = list(getattr(m5_bundle, "dark_path_hypotheses", []))
        dp_single = getattr(m5_bundle, "dark_path_hypothesis", None)
        if dp_single:
            dp_hypotheses.append(dp_single)

        intersects = False
        for dp in dp_hypotheses:
            paths = getattr(dp, "candidate_paths", getattr(dp, "paths", []))
            for p in paths:
                if getattr(p, "intersects_origin", False):
                    intersects = True
                    break

        lr, rat, src = self.compute_lr(
            "dark_path_origin",
            intersects,
            "dark_path_origin_intersection",
            "Dark path hypothesis labeled: HYPOTHESIS — reconstructed, not observed"
        )
        factors.append(LikelihoodRatioBreakdown(
            factor_name="dark_path_origin_intersection",
            factor_value="intersects" if intersects else "does_not_intersect",
            likelihood_ratio=lr,
            rationale=rat + " [HYPOTHESIS]",
            source_module=src
        ))
        
        return factors
    
    def apply_dependency_discounting(
        self,
        factors: List[LikelihoodRatioBreakdown]
    ) -> Dict[str, float]:
        """
        Apply dependency discounting to correlated factors.
        
        Returns: dict mapping group_name → effective_lr
        """
        effective_lrs = {}
        
        # Build factor lookup by name
        factor_map = {f.factor_name: f.likelihood_ratio for f in factors}
        
        for group_name, group_config in self.groups.items():
            group_factors = group_config["factors"]
            method = group_config["combination_method"]
            
            # Extract LRs for factors in this group
            group_lrs = [factor_map.get(fname, 1.0) for fname in group_factors if fname in factor_map]
            
            if not group_lrs:
                effective_lrs[group_name] = 1.0
                continue
            
            if method == "max":
                # Take maximum LR (most informative factor)
                effective_lrs[group_name] = max(group_lrs)
            
            elif method == "geometric_mean":
                # Geometric mean: (Π LRᵢ)^(1/N)
                product = 1.0
                for lr in group_lrs:
                    product *= lr
                effective_lrs[group_name] = product ** (1.0 / len(group_lrs))
            
            else:
                # Unknown method, default to product (no discount)
                effective_lrs[group_name] = math.prod(group_lrs)
        
        # Independent factors (not in any group) multiply directly
        grouped_factor_names = set()
        for group_config in self.groups.values():
            grouped_factor_names.update(group_config["factors"])
        
        independent_lrs = [
            f.likelihood_ratio 
            for f in factors 
            if f.factor_name not in grouped_factor_names
        ]
        
        effective_lrs["independent"] = math.prod(independent_lrs) if independent_lrs else 1.0
        
        return effective_lrs
    
    def compute_posterior(
        self,
        prior: float,
        factors: List[LikelihoodRatioBreakdown]
    ) -> float:
        """
        Compute posterior P(plausible source | evidence) via odds form.
        
        Posterior odds = Prior odds × Π effective_LR
        Posterior P = posterior_odds / (1 + posterior_odds)
        """
        # Prior odds
        if prior >= 1.0:
            prior_odds = float('inf')
        elif prior <= 0.0:
            prior_odds = 0.0
        else:
            prior_odds = prior / (1.0 - prior)
        
        # Apply dependency discounting
        effective_lrs = self.apply_dependency_discounting(factors)
        
        # Multiply all effective LRs
        total_lr = math.prod(effective_lrs.values())
        
        # Posterior odds
        posterior_odds = prior_odds * total_lr
        
        # Convert back to probability
        if math.isinf(posterior_odds):
            return 1.0
        else:
            posterior = posterior_odds / (1.0 + posterior_odds)
        
        return min(max(posterior, 0.0), 1.0)  # Clamp [0,1]
    
    def rank_vessel(
        self,
        vessel_id: str,
        m5_bundle: EvidenceBundleV1,
        m6_bundle: Optional[Module6VerificationBundleV1],
        m7_bundle: Optional[CounterfactualEvidenceBundleV1],
        case_context: Dict[str, Any],
        vessel_type: Optional[str] = None
    ) -> Tuple[float, float, List[LikelihoodRatioBreakdown]]:
        """
        Rank a single vessel.
        
        Returns: (prior, posterior, lr_breakdown)
        """
        # Determine if vessel was dark during release window
        is_dark = False
        if m6_bundle:
            is_dark = (m6_bundle.ais_state in [AisState.AIS_GAP_DARK, AisState.REPORTING_ANOMALY])
        
        # Get prior
        prior = self.get_prior(vessel_type=vessel_type, is_dark=is_dark)
        
        # Extract factors
        factors = self.extract_factors(
            vessel_id=vessel_id,
            m5_bundle=m5_bundle,
            m6_bundle=m6_bundle,
            m7_bundle=m7_bundle,
            case_context=case_context
        )
        
        # Compute posterior
        posterior = self.compute_posterior(prior, factors)
        
        return prior, posterior, factors
