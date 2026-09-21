"""
Module 3 — Environmental Velocity Field & Vector Hydrodynamics
Loads ocean current and wind datasets, applies advanced marine transport models
(Coriolis deflection, Stokes drift), and provides velocity lookups and Smagorinsky shear.
"""
import math
from pathlib import Path
from typing import Tuple, Union, Optional
import numpy as np

from config import OCEAN_DIR, WIND_DIR, WIND_DRIFT_COEFFICIENT
from drift.interpolation import bilinear_interpolate_vector
from drift.schemas import (
    VectorHydrodynamics, SurfaceCurrentInfo, WindLeewayInfo, NetAdvectionInfo
)

class VelocityField:
    """
    Advanced Environmental Velocity Field mapping:
    V_net = V_current + V_stokes + V_leeway(coriolis)
    """

    def __init__(
        self,
        ocean_path: Optional[Path] = None,
        wind_path: Optional[Path] = None,
        wind_leeway: float = WIND_DRIFT_COEFFICIENT,
        smagorinsky_constant: float = 0.15,
        grid_resolution_m: float = 9000.0  # ~1/12 degree HYCOM resolution
    ):
        ocean_file = ocean_path or (OCEAN_DIR / "current_arabian_sea.npz")
        wind_file = wind_path or (WIND_DIR / "wind_arabian_sea.npz")

        if not ocean_file.exists():
            raise FileNotFoundError(f"Ocean current file missing at {ocean_file}")
        if not wind_file.exists():
            raise FileNotFoundError(f"Wind file missing at {wind_file}")

        curr_data = np.load(ocean_file)
        wind_data = np.load(wind_file)

        self.lats = curr_data["lats"]
        self.lons = curr_data["lons"]
        self.curr_U = curr_data["U"]
        self.curr_V = curr_data["V"]

        self.wind_U = wind_data["U"]
        self.wind_V = wind_data["V"]

        self.wind_leeway_coeff = float(wind_leeway)

        # Advanced Physics: Stokes Drift (empirical 1.5% of wind speed)
        stokes_coeff = 0.015
        self.stokes_U = stokes_coeff * self.wind_U
        self.stokes_V = stokes_coeff * self.wind_V

        # Advanced Physics: Coriolis Deflection (15 degrees right in Northern Hemisphere)
        theta_rad = math.radians(-15.0)
        cos_t = math.cos(theta_rad)
        sin_t = math.sin(theta_rad)

        leeway_U_base = self.wind_leeway_coeff * self.wind_U
        leeway_V_base = self.wind_leeway_coeff * self.wind_V

        self.leeway_U = leeway_U_base * cos_t - leeway_V_base * sin_t
        self.leeway_V = leeway_U_base * sin_t + leeway_V_base * cos_t

        # Pre-compute total net velocity field on the grid
        self.net_U = self.curr_U + self.stokes_U + self.leeway_U
        self.net_V = self.curr_V + self.stokes_V + self.leeway_V

        # Calculate horizontal velocity gradients for Smagorinsky turbulence model
        dy = grid_resolution_m
        dx = grid_resolution_m  # Assuming approx isotropic grid in meters for shear estimation
        
        dU_dy, dU_dx = np.gradient(self.net_U, dy, dx)
        dV_dy, dV_dx = np.gradient(self.net_V, dy, dx)
        
        # Strain rate magnitude |S| = sqrt( 2(dU/dx)^2 + 2(dV/dy)^2 + (dU/dy + dV/dx)^2 )
        S = np.sqrt(2 * (dU_dx**2) + 2 * (dV_dy**2) + (dU_dy + dV_dx)**2)
        
        # Eddy diffusivity Kh = (Cs * Delta)^2 * |S|
        self.eddy_diff_Kh = (smagorinsky_constant * grid_resolution_m)**2 * S

    def get_velocity(
        self,
        lat: Union[float, np.ndarray],
        lon: Union[float, np.ndarray]
    ) -> Tuple[Union[float, np.ndarray], Union[float, np.ndarray]]:
        """
        Calculates the net surface transport velocity (u_net, v_net) in m/s at (lat, lon).
        """
        return bilinear_interpolate_vector(
            lat, lon, self.lats, self.lons, self.net_U, self.net_V
        )

    def get_eddy_diffusivity(
        self,
        lat: Union[float, np.ndarray],
        lon: Union[float, np.ndarray]
    ) -> Union[float, np.ndarray]:
        """
        Calculates local Smagorinsky eddy diffusivity Kh (m^2/s) at (lat, lon).
        """
        Kh, _ = bilinear_interpolate_vector(
            lat, lon, self.lats, self.lons, self.eddy_diff_Kh, np.zeros_like(self.eddy_diff_Kh)
        )
        return Kh

    def get_components_at(
        self,
        lat: float,
        lon: float
    ) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
        """
        Returns ((u_curr, v_curr), (u_wind_driven, v_wind_driven), (u_net, v_net)) at a specific location.
        """
        u_c, v_c = bilinear_interpolate_vector(lat, lon, self.lats, self.lons, self.curr_U, self.curr_V)
        # For the UI card, we combine Leeway + Stokes into the total wind-driven component
        u_w_driven = bilinear_interpolate_vector(lat, lon, self.lats, self.lons, self.leeway_U + self.stokes_U, self.leeway_V + self.stokes_V)[0]
        v_w_driven = bilinear_interpolate_vector(lat, lon, self.lats, self.lons, self.leeway_U + self.stokes_U, self.leeway_V + self.stokes_V)[1]
        
        u_raw_wind = bilinear_interpolate_vector(lat, lon, self.lats, self.lons, self.wind_U, self.wind_V)[0]
        v_raw_wind = bilinear_interpolate_vector(lat, lon, self.lats, self.lons, self.wind_U, self.wind_V)[1]

        u_n, v_n = bilinear_interpolate_vector(lat, lon, self.lats, self.lons, self.net_U, self.net_V)
        return (float(u_c), float(v_c)), (float(u_raw_wind), float(v_raw_wind)), (float(u_n), float(v_n))

    def get_vector_hydrodynamics(
        self,
        lat: float,
        lon: float,
        model_source: str = "HYCOM / GFS"
    ) -> VectorHydrodynamics:
        """
        Computes the Vector Hydrodynamics card data at a given coordinate.
        """
        (u_c, v_c), (u_raw_wind, v_raw_wind), (u_n, v_n) = self.get_components_at(lat, lon)

        def vector_metrics(u: float, v: float) -> Tuple[float, float]:
            speed = math.sqrt(u**2 + v**2)
            direction = (math.degrees(math.atan2(u, v)) + 360.0) % 360.0
            return speed, direction

        curr_speed, curr_dir = vector_metrics(u_c, v_c)
        raw_wind_speed, raw_wind_dir = vector_metrics(u_raw_wind, v_raw_wind)
        net_speed_mps, net_dir = vector_metrics(u_n, v_n)

        # Wind leeway component for display (in mockup it shows raw wind in knots, but we apply coefficient for math)
        wind_leeway_speed_kts = raw_wind_speed * 1.94384

        net_speed_kmh = net_speed_mps * 3.6
        net_speed_kts = net_speed_mps * 1.94384

        return VectorHydrodynamics(
            model_source=model_source,
            surface_current=SurfaceCurrentInfo(
                speed_mps=round(curr_speed, 2),
                direction_deg=round(curr_dir, 0),
                u_mps=round(u_c, 3),
                v_mps=round(v_c, 3),
            ),
            wind_leeway=WindLeewayInfo(
                speed_knots=round(wind_leeway_speed_kts, 1),
                speed_mps=round(raw_wind_speed, 2),
                direction_deg=round(raw_wind_dir, 0),
                u_mps=round(u_raw_wind, 3),
                v_mps=round(v_raw_wind, 3),
            ),
            net_advection=NetAdvectionInfo(
                speed_kmh=round(net_speed_kmh, 2),
                speed_knots=round(net_speed_kts, 2),
                speed_mps=round(net_speed_mps, 3),
                direction_deg=round(net_dir, 0),
                u_mps=round(u_n, 3),
                v_mps=round(v_n, 3),
            )
        )
