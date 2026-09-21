"""
Module 6 — Stage 4: Reachability Engine
(a) Inter-ping: consecutive reported positions vs class max + current assist.
(b) Round-trip dark check: d1 = geodesic(last_known, origin-zone boundary),
    d2 = geodesic(origin-zone boundary, next_known),
    required_kn = (d1+d2) / elapsed_h,
    limit_kn = class_max + conservative CMEMS tail component.
    Verdict: REACHABLE | POSSIBLY_REACHABLE (within margin_band_pct) | IMPLAUSIBLE.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from src.ais.schemas import (
    CaseContextV1,
    EvidenceBundleV1,
    ReachabilityResult,
    ReachabilityVerdict,
    VesselTrack,
    VerificationStageStatus,
)
from src.ais.track_builder import geodesic_distance_km


class ReachabilityEngine:
    """Stage 4: Physical reachability verification."""

    def __init__(self, config: Dict[str, Any]):
        reach_cfg = config.get("reachability", {})
        self.margin_band_pct = float(reach_cfg.get("margin_band_pct", 10))
        self.current_assist = bool(reach_cfg.get("current_assist", True))
        self.current_boost_kn = float(reach_cfg.get("current_boost_kn", 2.0))

        # Vessel class max speeds
        region_cfg = config.get("_region", {})
        self.vessel_max_speeds = region_cfg.get("vessel_class_max_speeds_kn", {"default": 18.0})

    def analyze(
        self,
        bundle: EvidenceBundleV1,
        context: CaseContextV1,
        track: Optional[VesselTrack] = None,
    ) -> ReachabilityResult:
        """Run reachability checks on vessel track and dark-period round trips."""
        vessel_id = bundle.vessel_id
        max_speed_kn = float(self.vessel_max_speeds.get("default", 18.0))
        limit_kn = max_speed_kn + (self.current_boost_kn if self.current_assist else 0.0)

        inter_ping_violations = 0
        round_trip_checks: List[Dict[str, Any]] = []

        if track and len(track.pings) >= 2:
            # (a) Inter-ping reachability
            for i in range(1, len(track.pings)):
                p1 = track.pings[i - 1]
                p2 = track.pings[i]
                dist_km = geodesic_distance_km(p1.lat, p1.lon, p2.lat, p2.lon)
                dt_h = max(0.001, (p2.timestamp - p1.timestamp).total_seconds() / 3600.0)
                required_kn = (dist_km / 1.852) / dt_h  # km to nm, then nm/h = knots

                if required_kn > limit_kn * (1 + self.margin_band_pct / 100.0):
                    inter_ping_violations += 1

        # (b) Round-trip dark checks for each gap
        if track and bundle.ais_gaps:
            origin_center = self._get_origin_center(context)

            for gap_idx, gap in enumerate(bundle.ais_gaps):
                if origin_center is None:
                    round_trip_checks.append({
                        "gap_id": f"gap_{gap_idx}",
                        "verdict": ReachabilityVerdict.REACHABLE.value,
                        "notes": "No origin zone provided — skipping round-trip check",
                    })
                    continue

                # d1: last known position → origin zone center
                d1_km = geodesic_distance_km(
                    gap.start_lat, gap.start_lon,
                    origin_center["lat"], origin_center["lon"],
                )
                # d2: origin zone center → next known position
                d2_km = geodesic_distance_km(
                    origin_center["lat"], origin_center["lon"],
                    gap.end_lat, gap.end_lon,
                )

                total_km = d1_km + d2_km
                elapsed_h = max(0.001, gap.duration_minutes / 60.0)
                required_kn = (total_km / 1.852) / elapsed_h
                margin_pct = ((limit_kn - required_kn) / limit_kn * 100) if limit_kn > 0 else 0

                if required_kn <= limit_kn:
                    verdict = ReachabilityVerdict.REACHABLE
                elif required_kn <= limit_kn * (1 + self.margin_band_pct / 100.0):
                    verdict = ReachabilityVerdict.POSSIBLY_REACHABLE
                else:
                    verdict = ReachabilityVerdict.IMPLAUSIBLE

                round_trip_checks.append({
                    "gap_id": f"gap_{gap_idx}",
                    "d1_km": round(d1_km, 2),
                    "d2_km": round(d2_km, 2),
                    "total_km": round(total_km, 2),
                    "required_kn": round(required_kn, 2),
                    "limit_kn": round(limit_kn, 2),
                    "margin_pct": round(margin_pct, 2),
                    "verdict": verdict.value,
                })

        # Overall verdict
        overall = ReachabilityVerdict.REACHABLE
        for check in round_trip_checks:
            v = check.get("verdict", ReachabilityVerdict.REACHABLE.value)
            if v == ReachabilityVerdict.IMPLAUSIBLE.value:
                overall = ReachabilityVerdict.IMPLAUSIBLE
                break
            elif v == ReachabilityVerdict.POSSIBLY_REACHABLE.value:
                overall = ReachabilityVerdict.POSSIBLY_REACHABLE

        if inter_ping_violations > 0 and overall == ReachabilityVerdict.REACHABLE:
            overall = ReachabilityVerdict.POSSIBLY_REACHABLE

        status = (
            VerificationStageStatus.FLAGGED
            if overall != ReachabilityVerdict.REACHABLE
            else VerificationStageStatus.PASSED
        )

        return ReachabilityResult(
            vessel_id=vessel_id,
            inter_ping_violations=inter_ping_violations,
            round_trip_dark_checks=round_trip_checks,
            overall_verdict=overall,
            status=status,
        )

    def _get_origin_center(self, context: CaseContextV1) -> Optional[Dict[str, float]]:
        """Extract origin zone center from case context."""
        if context.spill_center:
            return context.spill_center

        if context.origin_zones:
            zone = context.origin_zones[0]
            coords = zone.get("coordinates", [[]])
            if coords and coords[0]:
                ring = coords[0]
                avg_lon = sum(c[0] for c in ring) / len(ring)
                avg_lat = sum(c[1] for c in ring) / len(ring)
                return {"lat": avg_lat, "lon": avg_lon}

        return None
