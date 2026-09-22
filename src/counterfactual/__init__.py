"""
Module 7 — Counterfactual Trajectory Reasoning

Public API (lazy imports to avoid triggering VelocityField at import time):
    CounterfactualEngine — orchestrates the full pipeline for a case.
    load_counterfactual_config — loads config/counterfactual.yaml.

FORENSIC BOUNDARY:
    This module produces physical-consistency evidence.
    It does not produce guilt probabilities, causal attributions, or accusations.
"""

MODULE7_SCHEMA_VERSION = "1.0.0"


def __getattr__(name):
    """Lazy attribute lookup to avoid eager VelocityField imports at test collection."""
    if name == "CounterfactualEngine":
        from src.counterfactual.counterfactual_engine import CounterfactualEngine
        return CounterfactualEngine
    if name == "load_counterfactual_config":
        from src.counterfactual.counterfactual_engine import load_counterfactual_config
        return load_counterfactual_config
    if name == "CounterfactualEvidenceBundleV1":
        from src.counterfactual.schemas import CounterfactualEvidenceBundleV1
        return CounterfactualEvidenceBundleV1
    raise AttributeError(f"module 'src.counterfactual' has no attribute {name!r}")


__all__ = [
    "CounterfactualEngine",
    "load_counterfactual_config",
    "CounterfactualEvidenceBundleV1",
    "MODULE7_SCHEMA_VERSION",
]
