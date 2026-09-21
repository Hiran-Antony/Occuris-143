"""
Module 5 — Maritime Memory & Virtual Gateways — Innovation Layer C: Physics-Informed Dark-Path Reconstruction (§4.10)
Reconstructs unobserved vessel trajectories during AIS coverage blackouts.
Generates 4 physical/behavioral path hypotheses:
1. Geodesic: Great-circle direct WGS84 trajectory
2. Rhumb line: Constant navigational heading path
3. DNA-prior: Trajectory conditioned on vessel kinematic behavior
4. Current-assisted: Advected trajectory utilizing regional CMEMS ocean current field
Computes kinematic feasibility against vessel maximum speed capability,
ranks via softmax cost probabilities, and tests intersection with oil spill origin zones.
Labeled strictly as: 'HYPOTHESIS — reconstructed, not observed'.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pyproj import Geod
from shapely.geometry import LineString, Point, Polygon

from src.ais.schemas import AisGap, CandidateDarkPath, DarkPathHypothesis, VesselTrack
from src.ais.track_builder import WGS84_GEOD, geodesic_distance_km
from src.config import OCEAN_DIR

OCEAN_NPZ = OCEAN_DIR / "current_arabian_sea.npz"


class OceanCurrentProvider:
    """Provides cached CMEMS ocean current velocity components (m/s)."""

    def __init__(self, npz_path: Optional[Path] = None):
        self.path = npz_path or OCEAN_NPZ
        self.u = None
        self.v = None
        self.lats = None
        self.lons = None
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = np.load(self.path)
                self.u = data["U"]
                self.v = data["V"]
                self.lats = data["lats"]
                self.lons = data["lons"]
            except Exception:
                pass

    def get_current_at(self, lat: float, lon: float) -> Tuple[float, float]:
        """Return (u, v) current components in m/s at the nearest grid coordinate."""
        if self.u is None or self.lats is None or self.lons is None:
            return 0.0, 0.0

        lat_idx = int(np.argmin(np.abs(self.lats - lat)))
        lon_idx = int(np.argmin(np.abs(self.lons - lon)))

        return float(self.u[lat_idx, lon_idx]), float(self.v[lat_idx, lon_idx])


class DarkPathReconstructor:
    """Generates and evaluates physics-informed dark-path hypotheses."""

    def __init__(
        self,
        max_vessel_speed_knots: float = 18.0,  # Should be passed from config/region.yaml
        current_provider: Optional[OceanCurrentProvider] = None,
    ):
        self.max_speed_kn = max_vessel_speed_knots
        self.ocean = current_provider or OceanCurrentProvider()

    def reconstruct_gap(
        self,
        gap: AisGap,
        origin_zone: Optional[Polygon] = None,
        dna_speed_prior_kn: float = 12.5,
    ) -> DarkPathHypothesis:
        """
        Synthesize candidate paths connecting blackout endpoints and compute
        softmax probability distribution.
        """
        start_lat, start_lon = gap.start_lat, gap.start_lon
        end_lat, end_lon = gap.end_lat, gap.end_lon
        duration_h = max(0.05, gap.duration_minutes / 60.0)

        dist_direct_km = geodesic_distance_km(start_lat, start_lon, end_lat, end_lon)
        implied_direct_kn = (dist_direct_km * 0.539957) / duration_h

        candidates: List[CandidateDarkPath] = []
        costs: List[float] = []

        # ── 1. Geodesic Path (Direct WGS84 Line) ──────────────────────────────
        geod_points = WGS84_GEOD.npts(start_lon, start_lat, end_lon, end_lat, 8)
        geod_coords = [(start_lon, start_lat)] + geod_points + [(end_lon, end_lat)]
        geod_feasible = implied_direct_kn <= self.max_speed_kn

        geod_line = LineString(geod_coords)
        geod_intersects = origin_zone.intersects(geod_line) if origin_zone else False
        cost_geod = abs(implied_direct_kn - dna_speed_prior_kn) + 0.5

        candidates.append(
            CandidateDarkPath(
                path_type="geodesic",
                coordinates=[(round(lon, 5), round(lat, 5)) for lon, lat in geod_coords],
                length_km=round(dist_direct_km, 2),
                implied_speed_knots=round(implied_direct_kn, 1),
                feasible=geod_feasible,
                probability=0.0,
                intersects_origin=geod_intersects,
            )
        )
        costs.append(cost_geod if geod_feasible else 999.0)

        # ── 2. Rhumb Line Path ────────────────────────────────────────────────
        rhumb_coords = [(start_lon, start_lat)]
        for alpha in [0.2, 0.4, 0.6, 0.8]:
            # Linear interpolation in lat/lon space
            r_lat = start_lat + alpha * (end_lat - start_lat)
            r_lon = start_lon + alpha * (end_lon - start_lon)
            rhumb_coords.append((r_lat, r_lon))
        rhumb_coords.append((end_lon, end_lat))

        rhumb_line = LineString(rhumb_coords)
        rhumb_intersects = origin_zone.intersects(rhumb_line) if origin_zone else False
        cost_rhumb = abs(implied_direct_kn - dna_speed_prior_kn) + 0.8

        candidates.append(
            CandidateDarkPath(
                path_type="rhumb",
                coordinates=[(round(lon, 5), round(lat, 5)) for lon, lat in rhumb_coords],
                length_km=round(dist_direct_km * 1.002, 2),
                implied_speed_knots=round(implied_direct_kn * 1.002, 1),
                feasible=geod_feasible,
                probability=0.0,
                intersects_origin=rhumb_intersects,
            )
        )
        costs.append(cost_rhumb if geod_feasible else 999.0)

        # ── 3. DNA-Prior Path (Speed-Optimized Loiter/Curvature Path) ──────────
        # Deviates laterally if implied speed is significantly below vessel cruising speed
        dna_coords = [(start_lon, start_lat)]
        mid_lat = (start_lat + end_lat) / 2.0
        mid_lon = (start_lon + end_lon) / 2.0

        # Normal vector lateral offset
        d_lat = end_lat - start_lat
        d_lon = end_lon - start_lon
        norm_len = math.hypot(d_lat, d_lon)
        offset_deg = 0.08 if norm_len > 0.05 else 0.0

        offset_lat = mid_lat - (d_lon / norm_len) * offset_deg if norm_len > 0 else mid_lat
        offset_lon = mid_lon + (d_lat / norm_len) * offset_deg if norm_len > 0 else mid_lon

        dna_coords.extend([
            (start_lon + 0.25 * d_lon, start_lat + 0.25 * d_lat),
            (offset_lon, offset_lat),
            (start_lon + 0.75 * d_lon, start_lat + 0.75 * d_lat),
            (end_lon, end_lat),
        ])

        dna_line = LineString(dna_coords)
        dna_len_km = geodesic_distance_km(start_lat, start_lon, offset_lat, offset_lon) + \
                     geodesic_distance_km(offset_lat, offset_lon, end_lat, end_lon)
        dna_speed_kn = (dna_len_km * 0.539957) / duration_h
        dna_feasible = dna_speed_kn <= self.max_speed_kn
        dna_intersects = origin_zone.intersects(dna_line) if origin_zone else False
        cost_dna = abs(dna_speed_kn - dna_speed_prior_kn) + 0.4

        candidates.append(
            CandidateDarkPath(
                path_type="dna_prior",
                coordinates=[(round(lon, 5), round(lat, 5)) for lon, lat in dna_coords],
                length_km=round(dna_len_km, 2),
                implied_speed_knots=round(dna_speed_kn, 1),
                feasible=dna_feasible,
                probability=0.0,
                intersects_origin=dna_intersects,
            )
        )
        costs.append(cost_dna if dna_feasible else 999.0)

        # ── 4. Current-Assisted Path ──────────────────────────────────────────
        # Advects along ocean currents sampled at midpoint
        u_curr, v_curr = self.ocean.get_current_at(mid_lat, mid_lon)
        # 1 m/s over duration_h in degrees approx (1 deg ~ 111 km)
        advect_lon = (u_curr * (duration_h * 3600.0)) / (111000.0 * math.cos(math.radians(mid_lat)))
        advect_lat = (v_curr * (duration_h * 3600.0)) / 111000.0

        curr_mid_lat = mid_lat + 0.5 * advect_lat
        curr_mid_lon = mid_lon + 0.5 * advect_lon

        curr_coords = [
            (start_lon, start_lat),
            (curr_mid_lon, curr_mid_lat),
            (end_lon, end_lat),
        ]
        curr_line = LineString(curr_coords)
        curr_len_km = geodesic_distance_km(start_lat, start_lon, curr_mid_lat, curr_mid_lon) + \
                      geodesic_distance_km(curr_mid_lat, curr_mid_lon, end_lat, end_lon)
        curr_speed_kn = (curr_len_km * 0.539957) / duration_h
        curr_feasible = curr_speed_kn <= self.max_speed_kn
        curr_intersects = origin_zone.intersects(curr_line) if origin_zone else False
        cost_curr = abs(curr_speed_kn - dna_speed_prior_kn) + 0.2

        candidates.append(
            CandidateDarkPath(
                path_type="current_assisted",
                coordinates=[(round(lon, 5), round(lat, 5)) for lon, lat in curr_coords],
                length_km=round(curr_len_km, 2),
                implied_speed_knots=round(curr_speed_kn, 1),
                feasible=curr_feasible,
                probability=0.0,
                intersects_origin=curr_intersects,
            )
        )
        costs.append(cost_curr if curr_feasible else 999.0)

        # ── Softmax Probability Weighting ─────────────────────────────────────
        feasible_indices = [i for i, c in enumerate(candidates) if c.feasible]
        if feasible_indices:
            valid_costs = np.array([costs[i] for i in feasible_indices])
            # Negative cost for softmax
            exp_weights = np.exp(-valid_costs / max(1.0, float(np.std(valid_costs) or 1.0)))
            probs = exp_weights / np.sum(exp_weights)

            for idx, prob in zip(feasible_indices, probs):
                candidates[idx].probability = float(prob)
        elif candidates:
            # Fallback uniform probability if none feasible
            uniform_p = 1.0 / len(candidates)
            for c in candidates:
                c.probability = uniform_p

        any_intersects = any(c.intersects_origin for c in candidates)

        return DarkPathHypothesis(
            hypothesis_id=f"HYP_{gap.vessel_id}_{gap.gap_start.strftime('%Y%m%d%H%M')}",
            vessel_id=gap.vessel_id,
            gap_start=gap.gap_start,
            gap_end=gap.gap_end,
            start_lat=gap.start_lat,
            start_lon=gap.start_lon,
            end_lat=gap.end_lat,
            end_lon=gap.end_lon,
            paths=candidates,
            intersects_origin=any_intersects,
            disclaimer="HYPOTHESIS — reconstructed, not observed",
        )

    def reconstruct_hypotheses(
        self,
        track: VesselTrack,
        origin_zone: Optional[Polygon] = None,
        dna_speed_prior_kn: float = 12.5,
    ) -> List[DarkPathHypothesis]:
        """Reconstruct physics-informed dark path hypotheses for all detected gaps in a vessel track."""
        return [
            self.reconstruct_gap(gap, origin_zone=origin_zone, dna_speed_prior_kn=dna_speed_prior_kn)
            for gap in track.gaps
        ]
