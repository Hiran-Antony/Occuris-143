"""
Module 6 — Stage 2: AIS Continuity Analyzer
Consumes Module 5 gaps + computes windowed statistics (total dark minutes, gap count, max gap).
Computes gap_concurrency_index = fraction of OTHER vessels with overlapping gap ± window_min
within radius_nm. COVERAGE support flag when ≥ coverage_min_vessels.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.ais.schemas import (
    AisGap,
    CaseContextV1,
    ContinuityReport,
    EvidenceBundleV1,
    GapConcurrencyRecord,
    VerificationStageStatus,
)
from src.ais.track_builder import geodesic_distance_nm


class ContinuityAnalyzer:
    """Stage 2: Analyze AIS continuity gaps and compute concurrency index."""

    def __init__(self, config: Dict[str, Any]):
        conc = config.get("concurrency", {})
        self.window_min = float(conc.get("window_min", 15))
        self.coverage_min_vessels = int(conc.get("coverage_min_vessels", 3))
        self.radius_nm = float(conc.get("radius_nm", 20))

    def analyze(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
        all_bundles: List[EvidenceBundleV1],
    ) -> ContinuityReport:
        """Compute gap statistics and concurrency index for a single vessel."""
        gaps = bundle.ais_gaps
        vessel_id = bundle.vessel_id

        if not gaps:
            return ContinuityReport(
                vessel_id=vessel_id,
                total_gaps=0,
                total_dark_minutes=0.0,
                max_gap_minutes=0.0,
                gap_concurrency_index=0.0,
                gap_concurrency_records=[],
                coverage_support=False,
                status=VerificationStageStatus.PASSED,
            )

        total_dark = sum(g.duration_minutes for g in gaps)
        max_gap = max(g.duration_minutes for g in gaps)

        # Compute concurrency for each gap
        other_bundles = [b for b in all_bundles if b.vessel_id != vessel_id]
        concurrency_records: List[GapConcurrencyRecord] = []
        total_concurrent = 0

        for gap in gaps:
            concurrent_ids = self._find_concurrent_gaps(gap, other_bundles)
            is_coverage = len(concurrent_ids) >= self.coverage_min_vessels
            if concurrent_ids:
                total_concurrent += 1

            concurrency_records.append(
                GapConcurrencyRecord(
                    gap_start=gap.gap_start,
                    gap_end=gap.gap_end,
                    duration_minutes=gap.duration_minutes,
                    concurrent_vessel_count=len(concurrent_ids),
                    concurrent_vessel_ids=concurrent_ids,
                    coverage_flag=is_coverage,
                )
            )

        gap_concurrency_index = total_concurrent / len(gaps) if gaps else 0.0
        coverage_support = any(r.coverage_flag for r in concurrency_records)

        status = (
            VerificationStageStatus.FLAGGED if len(gaps) > 0 and not coverage_support
            else VerificationStageStatus.PASSED
        )

        return ContinuityReport(
            vessel_id=vessel_id,
            total_gaps=len(gaps),
            total_dark_minutes=round(total_dark, 2),
            max_gap_minutes=round(max_gap, 2),
            gap_concurrency_index=round(gap_concurrency_index, 4),
            gap_concurrency_records=concurrency_records,
            coverage_support=coverage_support,
            status=status,
        )

    def _find_concurrent_gaps(
        self, gap: AisGap, other_bundles: List[EvidenceBundleV1]
    ) -> List[str]:
        """Find other vessels with temporally and spatially overlapping gaps."""
        from datetime import timedelta

        pad = timedelta(minutes=self.window_min)
        gap_start_padded = gap.gap_start - pad
        gap_end_padded = gap.gap_end + pad

        gap_mid_lat = (gap.start_lat + gap.end_lat) / 2.0
        gap_mid_lon = (gap.start_lon + gap.end_lon) / 2.0

        concurrent_ids: List[str] = []
        for other in other_bundles:
            for og in other.ais_gaps:
                # Temporal overlap check
                if og.gap_start <= gap_end_padded and og.gap_end >= gap_start_padded:
                    # Spatial proximity check
                    other_mid_lat = (og.start_lat + og.end_lat) / 2.0
                    other_mid_lon = (og.start_lon + og.end_lon) / 2.0
                    dist_nm = geodesic_distance_nm(
                        gap_mid_lat, gap_mid_lon, other_mid_lat, other_mid_lon
                    )
                    if dist_nm <= self.radius_nm:
                        concurrent_ids.append(other.vessel_id)
                        break  # One match per vessel is sufficient

        return concurrent_ids
