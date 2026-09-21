"""
Module 6 — Stage 1: Investigation Window Resolver
Resolves per-vessel analysis window = intersection of release window ± window_pad_min
with the vessel's journey/presence period from the EvidenceBundleV1.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from src.ais.schemas import (
    CaseContextV1,
    EvidenceBundleV1,
    VerificationStageStatus,
    WindowResolution,
)


class WindowResolver:
    """Stage 1: Resolve per-vessel investigation window from case context and evidence."""

    def __init__(self, config: Dict[str, Any]):
        self.window_pad_min = float(config.get("window_pad_min", 60))

    def resolve(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
    ) -> WindowResolution:
        """Compute the intersection of the padded release window with the vessel's presence."""
        pad = timedelta(minutes=self.window_pad_min)

        # Padded release window
        release_start = context.release_window_start - pad
        release_end = context.release_window_end + pad

        # Ensure UTC
        if release_start.tzinfo is None:
            release_start = release_start.replace(tzinfo=timezone.utc)
        if release_end.tzinfo is None:
            release_end = release_end.replace(tzinfo=timezone.utc)

        # Vessel presence window from journey
        vessel_start = None
        vessel_end = None
        if bundle.journey:
            vessel_start = bundle.journey.entry_time
            vessel_end = bundle.journey.exit_time

        # If no journey times, check gaps for presence evidence
        if vessel_start is None and bundle.ais_gaps:
            vessel_start = min(g.gap_start for g in bundle.ais_gaps)
        if vessel_end is None and bundle.ais_gaps:
            vessel_end = max(g.gap_end for g in bundle.ais_gaps)

        # Compute intersection
        if vessel_start and vessel_end:
            if vessel_start.tzinfo is None:
                vessel_start = vessel_start.replace(tzinfo=timezone.utc)
            if vessel_end.tzinfo is None:
                vessel_end = vessel_end.replace(tzinfo=timezone.utc)

            window_start = max(release_start, vessel_start)
            window_end = min(release_end, vessel_end)
            vessel_present = window_start < window_end
            overlap_minutes = max(0.0, (window_end - window_start).total_seconds() / 60.0)
        else:
            # No vessel timing data — use full padded release window
            window_start = release_start
            window_end = release_end
            vessel_present = False
            overlap_minutes = 0.0

        # Origin zone reference
        origin_ref = None
        if context.origin_zones:
            origin_ref = context.origin_zones[0].get("id", context.case_id)

        status = (
            VerificationStageStatus.PASSED if vessel_present
            else VerificationStageStatus.SKIPPED
        )

        return WindowResolution(
            vessel_id=bundle.vessel_id,
            window_start=window_start,
            window_end=window_end,
            overlap_minutes=round(overlap_minutes, 2),
            vessel_present=vessel_present,
            origin_zone_ref=origin_ref,
            status=status,
        )
