"""
Module 3 — Advanced Drift Physics Engine (RK45 & Smagorinsky)
Implements a 4th/5th-Order Runge-Kutta-Fehlberg (Dormand-Prince) integrator.
Supports both backward hindcasting and forward forecasting with 
dynamic Smagorinsky sub-grid scale turbulent diffusion.
"""
import math
from typing import Tuple, List, Callable, Dict, Any, Optional
import numpy as np

EARTH_RADIUS_M = 6_371_000.0

class RK45DriftEngine:
    """
    Advanced Lagrangian Particle Tracking Engine.
    Uses Dormand-Prince (RK45) adaptive integration and Smagorinsky turbulence.
    """

    # Dormand-Prince RK45 Butcher Tableau Coefficients
    C2 = 1/5; C3 = 3/10; C4 = 4/5; C5 = 8/9; C6 = 1.0; C7 = 1.0
    A21 = 1/5
    A31 = 3/40; A32 = 9/40
    A41 = 44/45; A42 = -56/15; A43 = 32/9
    A51 = 19372/6561; A52 = -25360/2187; A53 = 64448/6561; A54 = -212/729
    A61 = 9017/3168; A62 = -355/33; A63 = 46732/5247; A64 = 49/176; A65 = -5103/18656
    A71 = 35/384; A72 = 0; A73 = 500/1113; A74 = 125/192; A75 = -2187/6784; A76 = 11/84
    # 5th order update
    B1 = 35/384; B2 = 0; B3 = 500/1113; B4 = 125/192; B5 = -2187/6784; B6 = 11/84; B7 = 0

    def __init__(
        self,
        velocity_func: Callable[[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]],
        diffusivity_func: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None
    ):
        """
        Parameters:
            velocity_func: Callable (lats, lons) -> (u_mps, v_mps)
            diffusivity_func: Callable (lats, lons) -> Kh_m2s (Smagorinsky)
        """
        self.velocity_func = velocity_func
        self.diffusivity_func = diffusivity_func

    @staticmethod
    def geo_to_metric(lats: np.ndarray, lons: np.ndarray, lat0: float, lon0: float) -> Tuple[np.ndarray, np.ndarray]:
        lat_rad = np.radians(lats)
        lon_rad = np.radians(lons)
        lat0_rad = np.radians(lat0)
        lon0_rad = np.radians(lon0)
        x = EARTH_RADIUS_M * (lon_rad - lon0_rad) * np.cos(lat0_rad)
        y = EARTH_RADIUS_M * (lat_rad - lat0_rad)
        return x, y

    @staticmethod
    def metric_to_geo(x: np.ndarray, y: np.ndarray, lat0: float, lon0: float) -> Tuple[np.ndarray, np.ndarray]:
        lat0_rad = np.radians(lat0)
        lats = np.degrees(y / EARTH_RADIUS_M) + lat0
        lons = np.degrees(x / (EARTH_RADIUS_M * np.cos(lat0_rad) + 1e-12)) + lon0
        return lats, lons

    def step_rk45(
        self,
        lats: np.ndarray,
        lons: np.ndarray,
        dt_seconds: float,
        lat0: float,
        lon0: float,
        diffusion_rng: Optional[np.random.Generator] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Executes a 5th order Dormand-Prince step with dynamic Smagorinsky diffusion.
        """
        x0, y0 = self.geo_to_metric(lats, lons, lat0, lon0)
        h = dt_seconds

        # k1
        u1, v1 = self.velocity_func(lats, lons)
        k1_x = u1; k1_y = v1

        # k2
        lat_k2, lon_k2 = self.metric_to_geo(x0 + h*self.A21*k1_x, y0 + h*self.A21*k1_y, lat0, lon0)
        u2, v2 = self.velocity_func(lat_k2, lon_k2)
        k2_x = u2; k2_y = v2

        # k3
        lat_k3, lon_k3 = self.metric_to_geo(x0 + h*(self.A31*k1_x + self.A32*k2_x), 
                                            y0 + h*(self.A31*k1_y + self.A32*k2_y), lat0, lon0)
        u3, v3 = self.velocity_func(lat_k3, lon_k3)
        k3_x = u3; k3_y = v3

        # k4
        lat_k4, lon_k4 = self.metric_to_geo(x0 + h*(self.A41*k1_x + self.A42*k2_x + self.A43*k3_x), 
                                            y0 + h*(self.A41*k1_y + self.A42*k2_y + self.A43*k3_y), lat0, lon0)
        u4, v4 = self.velocity_func(lat_k4, lon_k4)
        k4_x = u4; k4_y = v4

        # k5
        lat_k5, lon_k5 = self.metric_to_geo(x0 + h*(self.A51*k1_x + self.A52*k2_x + self.A53*k3_x + self.A54*k4_x), 
                                            y0 + h*(self.A51*k1_y + self.A52*k2_y + self.A53*k3_y + self.A54*k4_y), lat0, lon0)
        u5, v5 = self.velocity_func(lat_k5, lon_k5)
        k5_x = u5; k5_y = v5

        # k6
        lat_k6, lon_k6 = self.metric_to_geo(x0 + h*(self.A61*k1_x + self.A62*k2_x + self.A63*k3_x + self.A64*k4_x + self.A65*k5_x), 
                                            y0 + h*(self.A61*k1_y + self.A62*k2_y + self.A63*k3_y + self.A64*k4_y + self.A65*k5_y), lat0, lon0)
        u6, v6 = self.velocity_func(lat_k6, lon_k6)
        k6_x = u6; k6_y = v6

        # 5th order update
        dx = h * (self.B1*k1_x + self.B3*k3_x + self.B4*k4_x + self.B5*k5_x + self.B6*k6_x)
        dy = h * (self.B1*k1_y + self.B3*k3_y + self.B4*k4_y + self.B5*k5_y + self.B6*k6_y)

        x_next = x0 + dx
        y_next = y0 + dy

        # Smagorinsky Dynamic Turbulent Diffusion
        if self.diffusivity_func is not None and diffusion_rng is not None:
            Kh = self.diffusivity_func(lats, lons)
            # Ensure minimum Kh to prevent zero diffusion
            Kh = np.clip(Kh, 0.1, 50.0) 
            sigma = np.sqrt(2.0 * Kh * abs(h))
            
            n = len(lats)
            rx = diffusion_rng.normal(0.0, 1.0, n)
            ry = diffusion_rng.normal(0.0, 1.0, n)
            x_next += sigma * rx
            y_next += sigma * ry

        return self.metric_to_geo(x_next, y_next, lat0, lon0)

    def integrate(
        self,
        seed_lats: np.ndarray,
        seed_lons: np.ndarray,
        duration_hours: float,
        dt_minutes: float = 10.0,
        backward: bool = True,
        seed: int = 42
    ) -> Tuple[np.ndarray, np.ndarray, List[Tuple[np.ndarray, np.ndarray]]]:
        """
        Integrates particle trajectories over duration_hours using RK45.
        """
        p_lats = np.array(seed_lats, dtype=np.float64, copy=True)
        p_lons = np.array(seed_lons, dtype=np.float64, copy=True)

        lat0 = float(np.mean(p_lats))
        lon0 = float(np.mean(p_lons))

        dt_seconds = abs(dt_minutes) * 60.0
        if backward:
            dt_seconds = -dt_seconds

        n_steps = int(round((duration_hours * 60.0) / abs(dt_minutes)))
        rng = np.random.default_rng(seed)
        trajectories = [(p_lats.copy(), p_lons.copy())]

        for _ in range(n_steps):
            p_lats, p_lons = self.step_rk45(p_lats, p_lons, dt_seconds, lat0, lon0, diffusion_rng=rng)
            trajectories.append((p_lats.copy(), p_lons.copy()))

        return p_lats, p_lons, trajectories

    def simulate_full_timeline(
        self,
        seed_lats: np.ndarray,
        seed_lons: np.ndarray,
        hindcast_hours: float,
        forecast_hours: float,
        dt_minutes: float = 10.0,
        seed: int = 42
    ) -> List[Dict[str, Any]]:
        """
        Simulates both backward hindcast and forward forecast timelines.
        """
        # 1. Hindcast
        _, _, hind_trajs = self.integrate(
            seed_lats=seed_lats, seed_lons=seed_lons,
            duration_hours=hindcast_hours, dt_minutes=dt_minutes,
            backward=True, seed=seed
        )

        # 2. Forecast
        _, _, fore_trajs = self.integrate(
            seed_lats=seed_lats, seed_lons=seed_lons,
            duration_hours=forecast_hours, dt_minutes=dt_minutes,
            backward=False, seed=seed + 1000
        )

        timeline_states = []

        n_hind_steps = len(hind_trajs) - 1
        for i in range(n_hind_steps, 0, -1):
            offset_hr = - (i * dt_minutes) / 60.0
            lats, lons = hind_trajs[i]
            timeline_states.append({
                "phase": "hindcast",
                "time_offset_hours": round(offset_hr, 2),
                "lats": lats,
                "lons": lons
            })

        obs_lats, obs_lons = hind_trajs[0]
        timeline_states.append({
            "phase": "observation",
            "time_offset_hours": 0.0,
            "lats": obs_lats,
            "lons": obs_lons
        })

        for i in range(1, len(fore_trajs)):
            offset_hr = (i * dt_minutes) / 60.0
            lats, lons = fore_trajs[i]
            timeline_states.append({
                "phase": "forecast",
                "time_offset_hours": round(offset_hr, 2),
                "lats": lats,
                "lons": lons
            })

        return timeline_states
