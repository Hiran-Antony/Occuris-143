"""
Module 8 — Temporal Evidence Analysis

Evaluates overlap between the estimated release window and the vessel's presence.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.ais.schemas import Module6VerificationBundleV1
from src.investigation.schemas import TemporalEvidence, TemporalOverlap

def _parse_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))

def evaluate_temporal_evidence(
    case_cfg: Dict[str, Any],
    m6_bundle: Optional[Module6VerificationBundleV1]
) -> TemporalEvidence:
    """
    Evaluates whether the vessel was present during the estimated release window.
    Extracts the window from Case Context and matches it against M6's window resolver.
    """
    sar_time_iso = case_cfg["sar_timestamp"]
    t_sar = _parse_dt(sar_time_iso)
    release_window_hours = case_cfg.get("release_window_hours", 24)
    import datetime as dt
    t_window_start = t_sar - dt.timedelta(hours=release_window_hours)
    
    start_iso = t_window_start.isoformat()
    end_iso = t_sar.isoformat()
    
    # If no M6 bundle, there's no temporal overlap data available
    if not m6_bundle or not m6_bundle.window:
        return TemporalEvidence(
            overlap_status=TemporalOverlap.NO_TEMPORAL_OVERLAP,
            release_window_start_iso=start_iso,
            release_window_end_iso=end_iso,
            vessel_presence_start_iso=None,
            vessel_presence_end_iso=None,
            overlap_minutes=0.0
        )
    
    window_data = m6_bundle.window
    overlap_mins = window_data.overlap_minutes
    
    if overlap_mins > 60:
        status = TemporalOverlap.TEMPORAL_OVERLAP
    elif overlap_mins > 0:
        status = TemporalOverlap.PARTIAL_TEMPORAL_OVERLAP
    else:
        status = TemporalOverlap.NO_TEMPORAL_OVERLAP
        
    return TemporalEvidence(
        overlap_status=status,
        release_window_start_iso=start_iso,
        release_window_end_iso=end_iso,
        vessel_presence_start_iso=window_data.vessel_first_seen,
        vessel_presence_end_iso=window_data.vessel_last_seen,
        overlap_minutes=overlap_mins
    )
