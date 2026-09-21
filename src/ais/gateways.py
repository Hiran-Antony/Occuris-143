"""
Module 5 — Maritime Memory & Virtual Gateways — Gateway Corridors (§4.3)
Loads virtual narrow geofenced corridors strictly from /config/region.yaml.
Provides Shapely polygon geometry and standard GeoJSON exports for visualization and intersection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml
from shapely.geometry import Polygon, shape

from src.ais.schemas import GatewayCorridor
from src.config import ROOT

CONFIG_REGION_PATH = ROOT / "config" / "region.yaml"


class GatewayManager:
    """Manages virtual corridor geometries parsed from configuration."""

    def __init__(self, config_path: Optional[Union[Path, str, List[GatewayCorridor]]] = None):
        if isinstance(config_path, list):
            self.config_path = CONFIG_REGION_PATH
            self._gateways = list(config_path)
            self._geometries = {}
            for corridor in self._gateways:
                geom = shape(corridor.geometry_geojson)
                if not isinstance(geom, Polygon):
                    geom = geom.buffer(0.05)
                self._geometries[corridor.gateway_id] = geom
        else:
            self.config_path = Path(config_path or CONFIG_REGION_PATH)
            self._gateways: List[GatewayCorridor] = []
            self._geometries: Dict[str, Polygon] = {}
            self.load_from_config()

    def load_from_config(self) -> None:
        """Parse gateways strictly from YAML configuration (zero hardcoded coordinates)."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file missing: {self.config_path}")

        with open(self.config_path, mode="r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        raw_gateways = cfg.get("gateways", [])
        self._gateways = []
        self._geometries = {}

        for gw_dict in raw_gateways:
            corridor = GatewayCorridor(**gw_dict)
            self._gateways.append(corridor)

            # Build Shapely Polygon from GeoJSON geometry
            geom = shape(corridor.geometry_geojson)
            if not isinstance(geom, Polygon):
                geom = geom.buffer(0.05)  # Buffer if line or other
            self._geometries[corridor.gateway_id] = geom

    @property
    def gateways(self) -> List[GatewayCorridor]:
        return self._gateways

    def get_geometry(self, gateway_id: str) -> Optional[Polygon]:
        return self._geometries.get(gateway_id)

    def to_geojson(self) -> Dict[str, Any]:
        """
        Format corridors as a standard GeoJSON FeatureCollection
        suitable for MapLibre GL JS / Leaflet rendering.
        """
        features = []
        for gw in self._gateways:
            features.append(
                {
                    "type": "Feature",
                    "id": gw.gateway_id,
                    "properties": {
                        "gateway_id": gw.gateway_id,
                        "name": gw.name,
                        "orientation": gw.orientation,
                        "entry_side": gw.entry_side,
                        "exit_side": gw.exit_side,
                        "color": gw.color,
                    },
                    "geometry": gw.geometry_geojson,
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
        }


# Global helper instance
_manager_instance: Optional[GatewayManager] = None


def get_gateway_manager() -> GatewayManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = GatewayManager()
    return _manager_instance


def get_default_gateways() -> List[GatewayCorridor]:
    return get_gateway_manager().gateways


def gateways_to_geojson(gateways: Optional[List[GatewayCorridor]] = None) -> Dict[str, Any]:
    return get_gateway_manager().to_geojson()
