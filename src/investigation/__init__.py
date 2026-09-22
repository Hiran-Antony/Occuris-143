"""
Module 8 — Evidence Fusion & Investigation

Public API for Module 8.

FORENSIC BOUNDARY:
    This module synthesizes physical, temporal, and spatial evidence.
    It does not establish legal causation or guilt.
"""

from src.investigation.evidence_fusion import fuse_evidence
from src.investigation.evidence_graph import build_evidence_graph
from src.investigation.investigation_report import generate_report_text
from src.investigation.schemas import (
    InvestigationReportBundleV1,
    MODULE8_SCHEMA_VERSION,
)

__all__ = [
    "fuse_evidence",
    "build_evidence_graph",
    "generate_report_text",
    "InvestigationReportBundleV1",
    "MODULE8_SCHEMA_VERSION"
]
