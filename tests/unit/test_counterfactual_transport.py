"""
Tests — Module 7 Transport Physics

Validates the forward transport adapter against known analytical solutions.
All tests use the shared RK45DriftEngine from Module 3 (backward=False).
"""

import math
import numpy as np
import pytest

from src.drift.rk4 import RK45DriftEngine

EARTH_M = 6_371_000.0
SEED_LAT, SEED_LON = 17.5, 69.2
TOLERANCE_M = 100.0


def _metric_displacement(lat0, lon0, lat1, lon1):
    dlat_m = (lat1 - lat0) * (math.pi / 180.0) * EARTH_M
    dlon_m = (lon1 - lon0) * (math.pi / 180.0) * EARTH_M * math.cos(math.radians(lat0))
    return math.sqrt(dlat_m ** 2 + dlon_m ** 2)


class TestZeroVelocity:
    """Zero velocity → particle stays at release point."""

    def test_zero_velocity_forward(self):
        def zero_vel(lats, lons):
            return np.zeros_like(lats), np.zeros_like(lons)

        engine = RK45DriftEngine(velocity_func=zero_vel, diffusivity_func=None)
        n = 5
        lats = np.full(n, SEED_LAT)
        lons = np.full(n, SEED_LON)

        final_lats, final_lons, _ = engine.integrate(
            seed_lats=lats, seed_lons=lons,
            duration_hours=6.0, dt_minutes=10.0,
            backward=False, seed=0,
        )
        for i in range(n):
            d = _metric_displacement(lats[i], lons[i], final_lats[i], final_lons[i])
            assert d < TOLERANCE_M, f"Particle {i} moved {d:.1f} m with zero velocity."

    def test_zero_velocity_backward(self):
        """Zero velocity is direction-independent."""
        def zero_vel(lats, lons):
            return np.zeros_like(lats), np.zeros_like(lons)

        engine = RK45DriftEngine(velocity_func=zero_vel, diffusivity_func=None)
        lats = np.array([SEED_LAT])
        lons = np.array([SEED_LON])
        final_lats, final_lons, _ = engine.integrate(
            seed_lats=lats, seed_lons=lons,
            duration_hours=3.0, dt_minutes=10.0,
            backward=True, seed=0,
        )
        d = _metric_displacement(SEED_LAT, SEED_LON, final_lats[0], final_lons[0])
        assert d < TOLERANCE_M


class TestConstantCurrent:
    """Constant current → displacement matches v × t within 1%."""

    def _run_constant(self, u_mps, v_mps, duration_h=1.0):
        def const_vel(lats, lons):
            return np.full_like(lats, u_mps), np.full_like(lats, v_mps)

        engine = RK45DriftEngine(velocity_func=const_vel, diffusivity_func=None)
        lats = np.array([SEED_LAT])
        lons = np.array([SEED_LON])
        final_lats, final_lons, _ = engine.integrate(
            seed_lats=lats, seed_lons=lons,
            duration_hours=duration_h, dt_minutes=10.0,
            backward=False, seed=0,
        )
        return final_lats[0], final_lons[0]

    def test_northward_current(self):
        u, v = 0.0, 0.5   # 0.5 m/s northward
        final_lat, final_lon = self._run_constant(u, v, duration_h=1.0)
        expected_dy_m = v * 3600.0
        actual_dy_m = (final_lat - SEED_LAT) * (math.pi / 180.0) * EARTH_M
        assert abs(actual_dy_m - expected_dy_m) / expected_dy_m < 0.01

    def test_eastward_current(self):
        u, v = 0.5, 0.0   # 0.5 m/s eastward
        final_lat, final_lon = self._run_constant(u, v, duration_h=1.0)
        expected_dx_m = u * 3600.0
        actual_dx_m = (final_lon - SEED_LON) * (math.pi / 180.0) * EARTH_M * math.cos(
            math.radians(SEED_LAT)
        )
        assert abs(actual_dx_m - expected_dx_m) / expected_dx_m < 0.01


class TestForwardDirection:
    """backward=False → time increases → particles move in expected direction."""

    def test_positive_duration_required_in_transport_adapter(self):
        import pytest
        # Defer imports of transport/VelocityField to avoid eager data-file checks
        try:
            from src.drift.velocity_field import VelocityField
            vf = VelocityField()
        except (ImportError, FileNotFoundError):
            pytest.skip("Velocity field data not present — skipping integration test.")
            return

        from src.counterfactual.transport import forward_transport

        lats = np.array([SEED_LAT])
        lons = np.array([SEED_LON])
        with pytest.raises(ValueError, match="duration_hours"):
            forward_transport(vf, lats, lons, duration_hours=-1.0, dt_minutes=10.0)


class TestDeterminism:
    """Same seed → identical results."""

    def test_identical_seeds_produce_identical_trajectories(self):
        def vel(lats, lons):
            return np.full_like(lats, 0.3), np.full_like(lats, 0.2)

        engine = RK45DriftEngine(velocity_func=vel, diffusivity_func=None)
        lats = np.array([SEED_LAT, SEED_LAT + 0.1])
        lons = np.array([SEED_LON, SEED_LON + 0.1])

        f1, g1, _ = engine.integrate(lats.copy(), lons.copy(),
                                      duration_hours=2.0, dt_minutes=10.0,
                                      backward=False, seed=99)
        f2, g2, _ = engine.integrate(lats.copy(), lons.copy(),
                                      duration_hours=2.0, dt_minutes=10.0,
                                      backward=False, seed=99)
        np.testing.assert_array_equal(f1, f2)
        np.testing.assert_array_equal(g1, g2)

    def test_different_seeds_produce_different_trajectories_with_diffusion(self):
        """When diffusion is active, different seeds → different outcomes."""
        def vel(lats, lons):
            return np.zeros_like(lats), np.zeros_like(lats)

        def diffusivity(lats, lons):
            return np.full_like(lats, 10.0)  # large diffusivity for sensitivity

        engine = RK45DriftEngine(velocity_func=vel, diffusivity_func=diffusivity)
        lats = np.full(20, SEED_LAT)
        lons = np.full(20, SEED_LON)

        f1, _, _ = engine.integrate(lats.copy(), lons.copy(),
                                     duration_hours=1.0, dt_minutes=10.0,
                                     backward=False, seed=1)
        f2, _, _ = engine.integrate(lats.copy(), lons.copy(),
                                     duration_hours=1.0, dt_minutes=10.0,
                                     backward=False, seed=99999)
        # With large diffusion and different seeds, positions should differ
        assert not np.allclose(f1, f2), "Different seeds should produce different diffusion."
