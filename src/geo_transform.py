"""
Authoritative Geospatial Transform — Shared by Module 2, 3, and 4
===================================================================
Single source of truth for pixel ↔ geographic coordinate conversion.

The 256×256 PNG masks in this project represent synthetic SAR scenes
whose geographic extents are defined by the `spill_bbox` configured in
config.py for each case.  The SegFormer model resizes inputs to 256×256,
so a pixel's physical scale is NOT the SAR sensor resolution (10 m/px)
but the bbox extent divided by image dimension.

Rule: ONE transform shared by all modules.

    Module 2 (geometry)  — area, axes, centroid
    Module 3 (drift)     — particle seeding lat/lon
    Module 4 (SpillSplit)— particles_to_mask rasterisation

All use `GeoTransform(case_id)` from this file.
"""
import math
from typing import Tuple
import numpy as np

# Avoid circular imports: read CASES lazily
_CASES = None

def _cases():
    global _CASES
    if _CASES is None:
        from config import CASES
        _CASES = CASES
    return _CASES


M_PER_DEG_LAT = 111_320.0   # metres per degree latitude (constant)


class GeoTransform:
    """
    Pixel ↔ geographic coordinate transform derived from the case's spill_bbox
    and the image dimensions.

    Pixel convention:
        row 0       = lat_max  (top of image = north)
        row H-1     = lat_min  (bottom       = south)
        col 0       = lon_min  (left         = west)
        col W-1     = lon_max  (right        = east)

    Usage:
        gt = GeoTransform("case_03")
        lat, lon = gt.pixel_to_latlon(row=128, col=200)
        row, col = gt.latlon_to_pixel(lat=21.3, lon=62.0)
        m_per_row, m_per_col = gt.metres_per_pixel()
        area_km2 = gt.pixel_area_km2(n_pixels=43_000)
    """

    def __init__(self, case_id: str, image_h: int = 256, image_w: int = 256):
        cases = _cases()
        bbox = cases[case_id]["spill_bbox"]
        self.case_id  = case_id
        self.lat_max  = bbox["lat_max"]
        self.lat_min  = bbox["lat_min"]
        self.lon_min  = bbox["lon_min"]
        self.lon_max  = bbox["lon_max"]
        self.H        = image_h
        self.W        = image_w

        # Geographic extents
        self.lat_range_deg = self.lat_max - self.lat_min   # degrees
        self.lon_range_deg = self.lon_max - self.lon_min   # degrees

        # Centre latitude (for longitude → metre conversion)
        self.center_lat = (self.lat_max + self.lat_min) / 2.0
        self.m_per_deg_lon = M_PER_DEG_LAT * math.cos(math.radians(self.center_lat))

        # Metres per pixel (derived from bbox, NOT from SAR sensor resolution)
        self._m_per_row = (self.lat_range_deg * M_PER_DEG_LAT) / self.H
        self._m_per_col = (self.lon_range_deg * self.m_per_deg_lon) / self.W

        # km per pixel
        self._km_per_row = self._m_per_row / 1000.0
        self._km_per_col = self._m_per_col / 1000.0

    # ── Core transforms ───────────────────────────────────────────────────────

    def pixel_to_latlon(self, row: float, col: float) -> Tuple[float, float]:
        """Convert (row, col) pixel coordinates to (latitude, longitude)."""
        lat = self.lat_max - (row / self.H) * self.lat_range_deg
        lon = self.lon_min + (col / self.W) * self.lon_range_deg
        return float(lat), float(lon)

    def latlon_to_pixel(self, lat: float, lon: float) -> Tuple[float, float]:
        """Convert (lat, lon) to (row, col) pixel coordinates."""
        row = (self.lat_max - lat) / self.lat_range_deg * self.H
        col = (lon - self.lon_min) / self.lon_range_deg * self.W
        return float(row), float(col)

    def pixels_to_latlons(
        self, rows: np.ndarray, cols: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Vectorised pixel → geographic transform."""
        lats = self.lat_max - (rows / self.H) * self.lat_range_deg
        lons = self.lon_min + (cols / self.W) * self.lon_range_deg
        return lats.astype(np.float64), lons.astype(np.float64)

    def latlons_to_pixels(
        self, lats: np.ndarray, lons: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Vectorised geographic → pixel transform."""
        rows = (self.lat_max - lats) / self.lat_range_deg * self.H
        cols = (lons - self.lon_min) / self.lon_range_deg * self.W
        return rows.astype(np.float64), cols.astype(np.float64)

    # ── Scale information ─────────────────────────────────────────────────────

    def metres_per_pixel(self) -> Tuple[float, float]:
        """Returns (m_per_row, m_per_col) — bbox-derived, not sensor resolution."""
        return self._m_per_row, self._m_per_col

    def km_per_pixel(self) -> Tuple[float, float]:
        """Returns (km_per_row, km_per_col)."""
        return self._km_per_row, self._km_per_col

    def pixel_area_km2(self, n_pixels: int) -> float:
        """Physical area of n_pixels in km², using bbox-derived pixel scale."""
        return n_pixels * self._km_per_row * self._km_per_col

    def pixel_length_km(self, n_pixels_row: float, n_pixels_col: float = 0.0) -> float:
        """Convert a pixel-space vector to km distance."""
        dy_km = n_pixels_row * self._km_per_row
        dx_km = n_pixels_col * self._km_per_col
        return math.sqrt(dy_km ** 2 + dx_km ** 2)

    # ── Diagnostic summary ────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Returns a dict summarising this transform (for JSON output and logging)."""
        return {
            "case_id":          self.case_id,
            "image_size_px":    f"{self.W}×{self.H}",
            "bbox_lat":         f"{self.lat_min}–{self.lat_max}",
            "bbox_lon":         f"{self.lon_min}–{self.lon_max}",
            "geographic_width_km":  round(self.lon_range_deg * self.m_per_deg_lon / 1000, 2),
            "geographic_height_km": round(self.lat_range_deg * M_PER_DEG_LAT / 1000, 2),
            "m_per_row":        round(self._m_per_row, 2),
            "m_per_col":        round(self._m_per_col, 2),
            "km_per_row":       round(self._km_per_row, 4),
            "km_per_col":       round(self._km_per_col, 4),
            "transform_source": "spill_bbox / image_dimensions (authoritative)",
            "note": (
                "This transform is shared by Module 2 (area), Module 3 (seeding), "
                "and Module 4 (rasterisation). Do not use PIXEL_SCALE_M from config "
                "for spatial calculations; that is the SAR sensor resolution, not the "
                "image pixel geographic scale after resizing to 256×256."
            ),
        }

    def print_summary(self):
        s = self.summary()
        print(f"  GeoTransform({self.case_id})")
        print(f"    Image         : {s['image_size_px']}")
        print(f"    Bbox lat      : {s['bbox_lat']}")
        print(f"    Bbox lon      : {s['bbox_lon']}")
        print(f"    Geo width     : {s['geographic_width_km']} km")
        print(f"    Geo height    : {s['geographic_height_km']} km")
        print(f"    m/px (row)    : {s['m_per_row']} m/px")
        print(f"    m/px (col)    : {s['m_per_col']} m/px")
        print(f"    Source        : {s['transform_source']}")
