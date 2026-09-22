"""
Module 7 — Release Hypothesis Sampler

Constructs the discrete hypothesis space for a candidate vessel by sampling
release times and locations from the Module 4 release window and the
vessel's AIS/dark-path track.

Key design constraints:
    1. Release times are sampled at a configurable interval across the full
       release window — not just the midpoint.
    2. Release locations come from the vessel's actual track positions at each
       candidate release time.
    3. AIS_OBSERVED and DARK_PATH_RECONSTRUCTED locations are treated with
       different provenance labels — they are never silently equated.
    4. If the vessel has no track information within the release window,
       no hypotheses are generated (the vessel is not eligible).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.counterfactual.schemas import (
    CounterfactualHypothesis,
    ReleaseLocation,
    ReleaseMode,
    ReleaseSource,
)

ENVIRONMENT_VERSION = "ENV_01"  # version tag for the current VelocityField snapshot


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _interpolate_position(
    t: datetime,
    track_points: List[Dict[str, Any]],
) -> Optional[Tuple[float, float, ReleaseSource]]:
    """Linear interpolation of vessel position at time t.

    track_points must be a list of dicts with keys:
        timestamp (datetime, UTC), lat (float), lon (float),
        is_reconstructed (bool, optional — True for dark-path positions)

    Returns (lat, lon, source) or None if t is outside the track's temporal range.
    """
    if not track_points:
        return None

    # Sort by timestamp
    pts = sorted(track_points, key=lambda p: p["timestamp"])
    t0, t1 = pts[0]["timestamp"], pts[-1]["timestamp"]

    if t < t0 or t > t1:
        return None

    # Find bracket
    for i in range(len(pts) - 1):
        ta, tb = pts[i]["timestamp"], pts[i + 1]["timestamp"]
        if ta <= t <= tb:
            span = (tb - ta).total_seconds()
            if span < 1.0:
                lat = pts[i]["lat"]
                lon = pts[i]["lon"]
                src = pts[i].get("is_reconstructed", False)
            else:
                r = (t - ta).total_seconds() / span
                lat = pts[i]["lat"] + r * (pts[i + 1]["lat"] - pts[i]["lat"])
                lon = pts[i]["lon"] + r * (pts[i + 1]["lon"] - pts[i]["lon"])
                # If either bracket point is reconstructed, the interpolation is also
                src = pts[i].get("is_reconstructed", False) or pts[i + 1].get(
                    "is_reconstructed", False
                )
            source = (
                ReleaseSource.DARK_PATH_RECONSTRUCTED if src else ReleaseSource.AIS_OBSERVED
            )
            return lat, lon, source

    return None


def sample_hypotheses(
    vessel_id: str,
    release_window_start: datetime,
    release_window_end: datetime,
    time_step_hours: float,
    track_points: List[Dict[str, Any]],
    particle_count: int,
    ensemble_members: int,
) -> List[CounterfactualHypothesis]:
    """Build the full set of counterfactual hypotheses for one vessel.

    For each sampled release time:
        - Interpolate vessel position on its track.
        - Create one CounterfactualHypothesis with correct provenance.

    Parameters
    ----------
    vessel_id:
        Identifier from Module 6 bundle.
    release_window_start, release_window_end:
        From CaseContextV1 (Module 4 origin zone estimate).
    time_step_hours:
        Sampling interval (from config release.time_step_hours).
    track_points:
        Vessel positions from Module 5/6. Each dict has 'timestamp' (datetime),
        'lat', 'lon', and optionally 'is_reconstructed' (bool).
    particle_count:
        From config particles.count.
    ensemble_members:
        From config ensemble.members.

    Returns
    -------
    List of CounterfactualHypothesis. Empty if the vessel has no track
    information within the release window.
    """
    hypotheses: List[CounterfactualHypothesis] = []
    step = timedelta(hours=time_step_hours)
    t = release_window_start
    t_idx = 0

    while t <= release_window_end:
        result = _interpolate_position(t, track_points)
        if result is not None:
            lat, lon, source = result
            h_id = f"CF-{vessel_id}-T{t_idx:02d}"
            hypotheses.append(
                CounterfactualHypothesis(
                    hypothesis_id=h_id,
                    vessel_id=vessel_id,
                    release_time_iso=_iso(t),
                    release_location=ReleaseLocation(
                        lat=lat,
                        lon=lon,
                        source=source,
                        note=f"interpolated from vessel track at {_iso(t)}",
                    ),
                    release_mode=ReleaseMode.POINT,
                    environment_version=ENVIRONMENT_VERSION,
                    particle_count=particle_count,
                    ensemble_members=ensemble_members,
                )
            )
        t += step
        t_idx += 1

    return hypotheses
