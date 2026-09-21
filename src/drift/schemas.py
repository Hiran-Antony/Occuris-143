"""
Module 3 — Backward Drift & Forecast Schemas
Data models for RK4 hindcast + forecast drift simulation, Vector Hydrodynamics,
plume dispersion, and timeline milestone snapshots.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class SurfaceCurrentInfo:
    speed_mps: float
    direction_deg: float
    u_mps: Optional[float] = None
    v_mps: Optional[float] = None

@dataclass
class WindLeewayInfo:
    speed_knots: float
    speed_mps: float
    direction_deg: float
    u_mps: Optional[float] = None
    v_mps: Optional[float] = None

@dataclass
class NetAdvectionInfo:
    speed_kmh: float
    speed_knots: float
    speed_mps: float
    direction_deg: float
    u_mps: Optional[float] = None
    v_mps: Optional[float] = None

@dataclass
class VectorHydrodynamics:
    model_source: str
    surface_current: SurfaceCurrentInfo
    wind_leeway: WindLeewayInfo
    net_advection: NetAdvectionInfo

@dataclass
class OceanographicRegime:
    model_source: str
    regime_name: str
    sub_region: str
    sea_state: str
    sea_temp_c: float
    salinity_psu: float
    bathymetry_m: float

@dataclass
class AdiosWeathering:
    model_source: str
    evaporated_percent: float
    dispersion_percent: float
    water_content_percent: float
    remaining_slick_percent: float
    viscosity_cst: float
    slick_area_km2: float

@dataclass
class TimelineMilestone:
    id: str
    label: str
    time_offset_hours: float
    timestamp: str
    formatted_time: str
    plume_centroid: Dict[str, float]  # {"latitude": float, "longitude": float}
    plume_area_km2: float

@dataclass
class SimulationConfig:
    hindcast_hours: int
    forecast_hours: int
    time_step_minutes: int
    particle_count: int
    engine: str = "RK4"
    eddy_diffusivity_m2s: float = 2.0

@dataclass
class OriginZone:
    center_lat: float
    center_lon: float
    semi_major_km: float
    semi_minor_km: float
    angle_deg: float
    a_deg: float
    b_deg: float
    area_km2: float

@dataclass
class ReleaseTimeWindow:
    sar_timestamp: str
    release_start: str
    release_end: str
    window_hours: float

@dataclass
class TimestepState:
    step_index: int
    phase: str  # "hindcast", "observation", "forecast"
    time_offset_hours: float
    timestamp: str
    formatted_time: str
    plume_centroid: Dict[str, float]
    plume_area_km2: float
    particles: List[List[float]]  # [[lat, lon], ...]
    vector_hydrodynamics: Optional[VectorHydrodynamics] = None
    weathering: Optional[AdiosWeathering] = None

@dataclass
class TimelineRange:
    min_offset_hours: float
    max_offset_hours: float
    total_steps: int

@dataclass
class DriftResult:
    case_id: str
    sar_timestamp: str
    simulation: SimulationConfig
    vector_hydrodynamics: VectorHydrodynamics
    oceanographic_regime: OceanographicRegime
    milestones: List[TimelineMilestone]
    origin_zone: OriginZone
    release_time_window: ReleaseTimeWindow
    timeline_range: TimelineRange
    trajectory: List[TimestepState]
    preview_plot: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
