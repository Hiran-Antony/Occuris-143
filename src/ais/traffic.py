"""
Module 5 — Maritime Memory & Virtual Gateways — Traffic Density Analysis (§4.7, §4.12)
Calculates real AIS vessel density per fixed hourly temporal bin,
classifies HIGH density via the configured percentile threshold,
and provides the data foundation for adaptive gateway analysis.

Design choice: fixed (non-overlapping) hourly bins are used instead of sliding windows
for determinism and simpler percentile semantics — each ping contributes to exactly one bin.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from src.ais.schemas import AisPing, TrafficDensityBin, TrafficLevel


class TrafficAnalyzer:
    """Evaluates regional and corridor-specific maritime vessel density from real AIS records."""

    def __init__(
        self,
        bin_duration_minutes: int = 60,
        percentile_threshold: float = 75.0,
    ):
        self.bin_duration_minutes = bin_duration_minutes
        self.percentile_threshold = percentile_threshold
        # Computed after compute_density_bins; used by get_traffic_at_time
        self._high_cutoff: float = 2.0
        self._low_cutoff: float = 1.0

    def compute_density_bins(
        self,
        records: List[AisPing],
    ) -> List[TrafficDensityBin]:
        """Compute fixed (non-overlapping) hourly traffic density bins across the observation window."""
        if not records:
            return []

        sorted_records = sorted(records, key=lambda r: r.timestamp)
        t_start = sorted_records[0].timestamp
        t_end = sorted_records[-1].timestamp

        bins: List[TrafficDensityBin] = []
        counts: List[int] = []

        curr = t_start
        window_delta = timedelta(minutes=self.bin_duration_minutes)

        temp_bins = []
        while curr < t_end + window_delta:
            w_end = curr + window_delta
            active_vessels = {
                r.vessel_id
                for r in sorted_records
                if curr <= r.timestamp < w_end
            }
            c = len(active_vessels)
            counts.append(c)
            temp_bins.append((curr, w_end, c))
            curr += window_delta  # Fixed step = bin width (non-overlapping)

        # Determine percentile cutoffs from real observed bins
        self._high_cutoff = float(np.percentile(counts, self.percentile_threshold)) if counts else 2.0
        self._low_cutoff = float(np.percentile(counts, 25.0)) if counts else 1.0

        for w_start, w_end, count in temp_bins:
            if count >= self._high_cutoff and count > 1:
                p_class = "HIGH"
            elif count <= self._low_cutoff:
                p_class = "LOW"
            else:
                p_class = "NORMAL"

            bins.append(
                TrafficDensityBin(
                    gateway_id="REGIONAL_CORRIDOR",
                    window_start=w_start,
                    window_end=w_end,
                    vessel_count=count,
                    percentile_class=p_class,
                )
            )

        return bins

    def get_traffic_at_time(
        self,
        records: List[AisPing],
        target_time: datetime,
    ) -> Dict[str, Any]:
        """Query density and high-traffic flag for a specific timestamp using percentile-based cutoff."""
        w_start = target_time - timedelta(minutes=self.bin_duration_minutes)
        w_end = target_time

        active_vessels = {
            r.vessel_id
            for r in records
            if w_start <= r.timestamp <= w_end
        }
        count = len(active_vessels)

        # Use percentile-based cutoff computed from full dataset (no magic numbers)
        is_high = count >= self._high_cutoff
        if is_high:
            level = TrafficLevel.HIGH
        elif count >= 2:
            level = TrafficLevel.NORMAL
        else:
            level = TrafficLevel.LOW

        return {
            "vessel_count": count,
            "level": level,
            "is_high_density": is_high,
            "window_start": w_start.isoformat(),
            "window_end": w_end.isoformat(),
        }

