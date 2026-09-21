"""
Module 3 — Bilinear Field Interpolation
Provides robust bilinear interpolation for 2D regular grids (lat, lon) -> (U, V).
Supports both scalar and vectorized queries with boundary clamping.
"""
from typing import Tuple, Union
import numpy as np

def bilinear_interpolate_vector(
    lat: Union[float, np.ndarray],
    lon: Union[float, np.ndarray],
    lats: np.ndarray,
    lons: np.ndarray,
    U: np.ndarray,
    V: np.ndarray
) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
    """
    Interpolates U and V vector components on a regular lat/lon grid.
    
    Parameters:
        lat: Latitude(s) in degrees
        lon: Longitude(s) in degrees
        lats: 1D array of grid latitudes (ascending)
        lons: 1D array of grid longitudes (ascending)
        U: 2D array of U velocities (shape: [len(lats), len(lons)])
        V: 2D array of V velocities (shape: [len(lats), len(lons)])
        
    Returns:
        (u_interp, v_interp): Interpolated velocities in m/s
    """
    is_scalar = np.isscalar(lat)
    lat_arr = np.atleast_1d(np.asarray(lat, dtype=np.float64))
    lon_arr = np.atleast_1d(np.asarray(lon, dtype=np.float64))

    # Clamp coordinates to grid limits to prevent out-of-bounds indexing
    lat_clamped = np.clip(lat_arr, lats[0], lats[-1])
    lon_clamped = np.clip(lon_arr, lons[0], lons[-1])

    # Find lower-left grid cell indices
    i0 = np.searchsorted(lats, lat_clamped) - 1
    j0 = np.searchsorted(lons, lon_clamped) - 1
    i0 = np.clip(i0, 0, len(lats) - 2)
    j0 = np.clip(j0, 0, len(lons) - 2)
    i1 = i0 + 1
    j1 = j0 + 1

    # Fractional weights
    d_lat = lats[i1] - lats[i0]
    d_lon = lons[j1] - lons[j0]
    dy = (lat_clamped - lats[i0]) / np.where(d_lat == 0, 1e-12, d_lat)
    dx = (lon_clamped - lons[j0]) / np.where(d_lon == 0, 1e-12, d_lon)

    # 4 corner weights
    w00 = (1.0 - dy) * (1.0 - dx)
    w10 = dy * (1.0 - dx)
    w01 = (1.0 - dy) * dx
    w11 = dy * dx

    # Interpolate U
    u_out = (
        U[i0, j0] * w00 +
        U[i1, j0] * w10 +
        U[i0, j1] * w01 +
        U[i1, j1] * w11
    )

    # Interpolate V
    v_out = (
        V[i0, j0] * w00 +
        V[i1, j0] * w10 +
        V[i0, j1] * w01 +
        V[i1, j1] * w11
    )

    if is_scalar:
        return float(u_out[0]), float(v_out[0])
    return u_out, v_out
