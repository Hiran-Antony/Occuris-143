"""
Module 6 — Verification Pipeline Orchestrator
Runs stages 1–6 sequentially. Stages consume only bundle + context (parallel-safe).
Emits Module6VerificationBundleV1. Deterministic ordering guaranteed.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.ais.schemas import (
    AisState,
    CaseContextV1,
    EvidenceBundleV1,
    Module6VerificationBundleV1,
    VesselTrack,
)
from src.verification.continuity_analyzer import ContinuityAnalyzer
from src.verification.dark_path_validator import DarkPathValidator
from src.verification.kinematic_engine import KinematicEngine
from src.verification.reachability_engine import ReachabilityEngine
from src.verification.state_classifier import StateClassifier
from src.verification.window_resolver import WindowResolver

MODULE6_VERSION = "6.0.0"


def load_verification_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load config/verification.yaml and merge with region config."""
    from src.config import ROOT

    vpath = config_path or (ROOT / "config" / "verification.yaml")
    rpath = ROOT / "config" / "region.yaml"

    config: Dict[str, Any] = {}
    if vpath.exists():
        with open(vpath, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Merge region config under _region key (read-only reference)
    if rpath.exists():
        with open(rpath, "r", encoding="utf-8") as f:
            region = yaml.safe_load(f) or {}
            config["_region"] = region

    return config


class VerificationPipeline:
    """Orchestrates the 6-stage AIS verification pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_verification_config()

        self.window_resolver = WindowResolver(self.config)
        self.continuity_analyzer = ContinuityAnalyzer(self.config)
        self.kinematic_engine = KinematicEngine(self.config)
        self.reachability_engine = ReachabilityEngine(self.config)
        self.dark_path_validator = DarkPathValidator(self.config)
        self.state_classifier = StateClassifier(self.config)

    def run(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
        track: Optional[VesselTrack] = None,
        all_bundles: Optional[List[EvidenceBundleV1]] = None,
        all_tracks: Optional[Dict[str, VesselTrack]] = None,
    ) -> Module6VerificationBundleV1:
        """Execute the full 6-stage verification pipeline for a single vessel.

        Args:
            bundle: Frozen Module 5 evidence for this vessel.
            context: Investigation case context.
            track: Vessel track (optional, for kinematic analysis).
            all_bundles: All vessel bundles (for concurrency analysis).
            all_tracks: All vessel tracks (for identity conflict detection).

        Returns:
            Module6VerificationBundleV1 with all stage results and classifications.
        """
        bundles = all_bundles or [bundle]

        # Stage 1: Window Resolution
        window = self.window_resolver.resolve(bundle, context)

        # Stage 2: Continuity Analysis
        continuity = self.continuity_analyzer.analyze(bundle, context, bundles)

        # Stage 3: Kinematic Consistency
        kinematic = self.kinematic_engine.analyze(
            bundle, context, track=track, all_tracks=all_tracks
        )

        # Stage 4: Reachability
        reachability = self.reachability_engine.analyze(bundle, context, track=track)

        # Stage 5: Dark-Path Validation
        dark_path = self.dark_path_validator.validate(bundle, context)

        # Stage 6: State Classification (aggregator)
        classification_result = self.state_classifier.classify(
            bundle, context, window, continuity, kinematic, reachability, dark_path
        )

        # Assemble output bundle
        result = Module6VerificationBundleV1(
            case_id=context.case_id,
            vessel_id=bundle.vessel_id,
            module6_version=MODULE6_VERSION,
            window=window,
            continuity=continuity,
            kinematic=kinematic,
            reachability=reachability,
            dark_path=dark_path,
            anomaly_classifications=classification_result["anomaly_classifications"],
            ais_state=classification_result["ais_state"],
            integrity_score=classification_result["integrity_score"],
            integrity_interval=classification_result["integrity_interval"],
            integrity_method=classification_result["integrity_method"],
            concealment_pattern_likelihood=classification_result["concealment_pattern_likelihood"],
            concealment_interval=classification_result["concealment_interval"],
            explanation_distribution=classification_result["explanation_distribution"],
            review_priority=classification_result["review_priority"],
            source_mode=bundle.source_mode,
        )

        return result

    def run_case(
        self,
        bundles: List[EvidenceBundleV1],
        context: CaseContextV1,
        tracks: Optional[Dict[str, VesselTrack]] = None,
    ) -> List[Module6VerificationBundleV1]:
        """Run verification pipeline for all vessels in a case."""
        results: List[Module6VerificationBundleV1] = []

        for bundle in bundles:
            track = tracks.get(bundle.vessel_id) if tracks else None
            result = self.run(
                bundle=bundle,
                context=context,
                track=track,
                all_bundles=bundles,
                all_tracks=tracks,
            )
            results.append(result)

        return results
