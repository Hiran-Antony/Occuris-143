"""
Module 3 — Origin Zone Estimation & Plume Dispersion Statistics
Computes 2-sigma Probable Origin Zone ellipses and per-timestep plume statistics
(Centroid & Area in km²) for timeline scrubbing.
"""
import math
import datetime
from typing import Tuple, Dict, Any
import numpy as np

from drift.rk4 import EARTH_RADIUS_M
from drift.schemas import OriginZone, ReleaseTimeWindow

def compute_plume_stats(lats: np.ndarray, lons: np.ndarray) -> Tuple[float, float, float]:
    """
    Computes (centroid_lat, centroid_lon, area_km2) for a cloud of particles.
    Area is determined by the 2-sigma dispersion ellipse in metric space.
    """
    c_lat = float(np.mean(lats))
    c_lon = float(np.mean(lons))

    lat_rad = np.radians(lats)
    lon_rad = np.radians(lons)
    c_lat_rad = np.radians(c_lat)
    c_lon_rad = np.radians(c_lon)

    x = EARTH_RADIUS_M * (lon_rad - c_lon_rad) * np.cos(c_lat_rad)
    y = EARTH_RADIUS_M * (lat_rad - c_lat_rad)

    pts = np.column_stack([x, y])
    if len(pts) < 3:
        return round(c_lat, 5), round(c_lon, 5), 0.1

    cov = np.cov(pts.T)
    evals = np.linalg.eigvalsh(cov)
    a_m = 2.0 * np.sqrt(max(float(evals[1]), 1e-4))
    b_m = 2.0 * np.sqrt(max(float(evals[0]), 1e-4))

    area_km2 = float(np.pi * (a_m / 1000.0) * (b_m / 1000.0))
    return round(c_lat, 5), round(c_lon, 5), round(area_km2, 2)


def fit_origin_ellipse(origin_lats: np.ndarray, origin_lons: np.ndarray) -> OriginZone:
    """
    Fits a 2-sigma (95% confidence) covariance ellipse to the origin particle cloud.
    Performs covariance analysis in local metric coordinates (meters) to avoid
    geodesic distortion, then maps back to degrees.
    """
    center_lat = float(np.mean(origin_lats))
    center_lon = float(np.mean(origin_lons))

    lat_rad = np.radians(origin_lats)
    lon_rad = np.radians(origin_lons)
    c_lat_rad = np.radians(center_lat)
    c_lon_rad = np.radians(center_lon)

    x = EARTH_RADIUS_M * (lon_rad - c_lon_rad) * np.cos(c_lat_rad)
    y = EARTH_RADIUS_M * (lat_rad - c_lat_rad)

    pts = np.column_stack([x, y])
    cov = np.cov(pts.T)

    evals, evecs = np.linalg.eigh(cov)
    order = evals.argsort()[::-1]
    evals, evecs = evals[order], evecs[:, order]

    a_meters = 2.0 * np.sqrt(max(float(evals[0]), 1e-4))
    b_meters = 2.0 * np.sqrt(max(float(evals[1]), 1e-4))

    a_km = a_meters / 1000.0
    b_km = b_meters / 1000.0

    angle_deg = float(np.degrees(np.arctan2(evecs[1, 0], evecs[0, 0])))

    m_per_deg_lat = (np.pi / 180.0) * EARTH_RADIUS_M
    m_per_deg_lon = m_per_deg_lat * np.cos(c_lat_rad)

    a_deg = a_meters / m_per_deg_lat
    b_deg = b_meters / m_per_deg_lon

    area_km2 = float(np.pi * a_km * b_km)

    return OriginZone(
        center_lat=round(center_lat, 5),
        center_lon=round(center_lon, 5),
        semi_major_km=round(a_km, 3),
        semi_minor_km=round(b_km, 3),
        angle_deg=round(angle_deg, 2),
        a_deg=round(a_deg, 6),
        b_deg=round(b_deg, 6),
        area_km2=round(area_km2, 3),
    )


def compute_release_window(
    sar_timestamp: str,
    drift_hours: float,
    buffer_hours: float = 2.0
) -> ReleaseTimeWindow:
    """
    Computes the temporal release window based on SAR timestamp and drift duration.
    """
    ts_clean = sar_timestamp.replace("Z", "+00:00")
    sar_dt = datetime.datetime.fromisoformat(ts_clean)

    center_release = sar_dt - datetime.timedelta(hours=drift_hours)
    release_start = center_release - datetime.timedelta(hours=buffer_hours)
    release_end = center_release + datetime.timedelta(hours=buffer_hours)

    window_hours = (release_end - release_start).total_seconds() / 3600.0

    return ReleaseTimeWindow(
        sar_timestamp=sar_timestamp,
        release_start=release_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        release_end=release_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_hours=round(window_hours, 1),
    )
