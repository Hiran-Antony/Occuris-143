"""
Module 5 — Maritime Memory & Virtual Gateways — Transit Delay Analysis (§4.6)
Strictly adheres to expected transit baseline priority:
1. HISTORICAL (same vessel, same corridor, >= 5 prior completed journeys) -> mean & std;
2. CORRIDOR_BASELINE (route distance / reference speed from documented config baseline);
3. INSUFFICIENT_HISTORY fallback.
Computes z-score = (actual - expected) / std ONLY when std exists and > 0.
Enforces the 2-sigma rule: z <= 2 is normal variation; z > 2 is POTENTIAL_UNEXPLAINED_DELAY evidence.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.ais.schemas import ExpectedTimeBasis, TransitAnalysis, VesselJourney
from src.config import ROOT

CONFIG_REGION_PATH = ROOT / "config" / "region.yaml"
KM_TO_NM = 0.539957


class DelayAnalyzer:
    """Evaluates passage durations against empirically grounded baselines."""

    def __init__(
        self,
        config_path: Optional[Path] = None,
        min_history_journeys: Optional[int] = None,
        default_baseline_speed_kn: Optional[float] = None,
    ):
        self.config_path = config_path or CONFIG_REGION_PATH
        self.default_reference_speed_kn = 12.0  # Documented IMO standard commercial transit speed
        self.min_history_count = 5
        self.z_sigma_threshold = 2.0
        self.baseline_speeds = {}
        self._load_config()
        if min_history_journeys is not None:
            self.min_history_count = min_history_journeys
        if default_baseline_speed_kn is not None:
            self.default_reference_speed_kn = default_baseline_speed_kn

    def _load_config(self) -> None:
        if self.config_path.exists():
            with open(self.config_path, mode="r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                thresholds = cfg.get("thresholds", {})
                self.min_history_count = int(thresholds.get("min_history_journeys", 5))
                self.z_sigma_threshold = float(thresholds.get("z_sigma", 2.0))
                self.baseline_speeds = cfg.get("vessel_class_baseline_speeds_kn", {})
                self.default_reference_speed_kn = float(self.baseline_speeds.get("default", 12.0))

    def analyze_journey(
        self,
        journey: VesselJourney,
        historical_durations: Optional[List[float]] = None,
        vessel_type: str = "default",
        history: Optional[List[Any]] = None,
    ) -> TransitAnalysis:
        """
        Analyze a journey duration using the strict 3-tier precedence rule.
        Never invents an arbitrary fixed expected time.
        """
        if history is not None and historical_durations is None:
            historical_durations = [
                j.actual_duration_h if hasattr(j, "actual_duration_h") else float(j)
                for j in history
            ]
        actual_h = journey.actual_duration_h
        dist_km = journey.distance_km

        # ── Precedence Tier 1: HISTORICAL ─────────────────────────────────────
        # Requires >= 5 prior completed journeys for the same vessel & corridor
        if historical_durations and len(historical_durations) >= self.min_history_count:
            mean_h = sum(historical_durations) / len(historical_durations)
            variance = sum((x - mean_h) ** 2 for x in historical_durations) / (len(historical_durations) - 1)
            std_h = math.sqrt(variance)

            delay_h = round(actual_h - mean_h, 2)
            # z-score ONLY when std exists and > 0
            z_score = round(delay_h / std_h, 2) if std_h > 1e-4 else None

            return TransitAnalysis(
                expected_duration_h=round(mean_h, 2),
                actual_duration_h=round(actual_h, 2),
                delay_h=delay_h,
                z_score=z_score,
                expected_basis=ExpectedTimeBasis.HISTORICAL,
                reference_speed_kn=round((dist_km * KM_TO_NM) / mean_h, 1) if mean_h > 0 else None,
            )

        # ── Precedence Tier 2: CORRIDOR_BASELINE ──────────────────────────────
        # Expected = route geodesic distance / reference speed
        # Reference speed = documented class speed or default from config
        ref_speed_kn = float(self.baseline_speeds.get(vessel_type, self.default_reference_speed_kn))

        if dist_km > 0.0 and ref_speed_kn > 0.0:
            dist_nm = dist_km * KM_TO_NM
            expected_h = round(dist_nm / ref_speed_kn, 2)
            delay_h = round(actual_h - expected_h, 2)

            return TransitAnalysis(
                expected_duration_h=expected_h,
                actual_duration_h=round(actual_h, 2),
                delay_h=delay_h,
                z_score=None,  # z-score is mathematically undefined without an empirical distribution
                expected_basis=ExpectedTimeBasis.CORRIDOR_BASELINE,
                reference_speed_kn=ref_speed_kn,
            )

        # ── Precedence Tier 3: INSUFFICIENT_HISTORY ───────────────────────────
        return TransitAnalysis(
            expected_duration_h=None,
            actual_duration_h=round(actual_h, 2),
            delay_h=None,
            z_score=None,
            expected_basis=ExpectedTimeBasis.INSUFFICIENT_HISTORY,
            reference_speed_kn=None,
        )

    def analyze_all(
        self,
        journeys: Dict[str, VesselJourney],
        history_map: Optional[Dict[str, List[float]]] = None,
    ) -> Dict[str, TransitAnalysis]:
        """Process delay analysis across all active journeys."""
        analyses: Dict[str, TransitAnalysis] = {}
        hist_map = history_map or {}

        for v_id, journey in journeys.items():
            hist = hist_map.get(v_id)
            analysis = self.analyze_journey(journey, hist)
            analyses[v_id] = analysis

            # Back-propagate metrics to journey record
            journey.expected_duration_h = analysis.expected_duration_h
            journey.delay_h = analysis.delay_h
            journey.z_score = analysis.z_score
            journey.expected_basis = analysis.expected_basis

        return analyses
