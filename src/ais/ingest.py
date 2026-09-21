"""
Module 5 — Maritime Memory & Virtual Gateways — Ingestion & Validation Layer (§4.1)
Implements AisSource interface with CsvReplaySource and LiveFeedSource stub.
Enforces UTC normalization, coordinate validation, and non-destructive physical plausibility flagging.
"""

from __future__ import annotations

import abc
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from src.ais.schemas import AisPing, AisSourceMode
from src.config import AIS_CSV


class AisSource(abc.ABC):
    """Abstract interface for ingesting AIS data streams."""

    @abc.abstractmethod
    def load(self) -> List[AisPing]:
        """Load and return all validated AIS records, ordered by (vessel_id, timestamp)."""
        pass

    @property
    @abc.abstractmethod
    def source_mode(self) -> AisSourceMode:
        """Active source mode enum ({SYNTHETIC_REPLAY, LIVE_FEED})."""
        pass

    @property
    @abc.abstractmethod
    def source_label(self) -> str:
        """Descriptive label for UI badge and provenance display."""
        pass


class CsvReplaySource(AisSource):
    """
    Ingests AIS data from a local CSV file, strictly validating coordinates,
    normalizing timestamps to UTC ISO-8601, and flagging physically impossible records.
    """

    def __init__(self, csv_path: Optional[Union[str, Path]] = None):
        self.csv_path = Path(csv_path or AIS_CSV)
        self._total_pings = 0

    @property
    def source_mode(self) -> AisSourceMode:
        return AisSourceMode.SYNTHETIC_REPLAY

    @property
    def is_live(self) -> bool:
        return False

    @property
    def total_pings(self) -> int:
        return self._total_pings

    @property
    def source_label(self) -> str:
        return f"Synthetic AIS Replay ({self.csv_path.name})"

    def load(self) -> List[AisPing]:
        if not self.csv_path.exists():
            self._total_pings = 0
            return []

        records: List[AisPing] = []
        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # 1. Parse and normalize timestamp to UTC
                    raw_ts = row["timestamp"].strip()
                    if raw_ts.endswith("Z"):
                        raw_ts = raw_ts[:-1] + "+00:00"
                    dt = datetime.fromisoformat(raw_ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)

                    # 2. Parse coordinates
                    lat = float(row["lat"])
                    lon = float(row["lon"])

                    # Drop malformed coordinate rows
                    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                        continue

                    sog = float(row.get("sog", 0.0) or 0.0)
                    cog = float(row.get("cog", 0.0) or 0.0)
                    nav_status = int(row.get("nav_status", 0) or 0)
                    mmsi = int(row["mmsi"])
                    vessel_id = str(row["vessel_id"]).strip()
                    vessel_name = str(row.get("vessel_name", "")).strip()
                    source_tag = str(row.get("source", "AIS_CSV")).strip()

                    # 3. Flag (do not drop) physically impossible records
                    # e.g. commercial vessel speed exceeding 65 knots
                    physically_impossible = sog < 0.0 or sog > 65.0 or cog < 0.0 or cog > 360.0

                    ping = AisPing(
                        mmsi=mmsi,
                        vessel_id=vessel_id,
                        vessel_name=vessel_name,
                        timestamp=dt,
                        lat=lat,
                        lon=lon,
                        sog=sog,
                        cog=cog,
                        nav_status=nav_status,
                        source=source_tag,
                        physically_impossible=physically_impossible,
                    )
                    records.append(ping)
                except (KeyError, ValueError):
                    # Drop malformed row
                    continue

        # Sort deterministically by vessel_id, then timestamp
        records.sort(key=lambda p: (p.vessel_id, p.timestamp))
        self._total_pings = len(records)
        return records

    load_records = load


class LiveFeedSource(AisSource):
    """
    Streaming AIS ingestion source (e.g. NMEA over TCP, AIVDM, or WebSockets).
    Allows plugging live maritime feeds without rewriting the engine.
    """

    def __init__(
        self,
        endpoint_url: str = "tcp://localhost:10110",
        source_label: Optional[str] = None,
    ):
        self.endpoint_url = endpoint_url
        self._source_label = source_label
        self._pings: List[AisPing] = []

    @property
    def is_live(self) -> bool:
        return True

    @property
    def total_pings(self) -> int:
        return len(self._pings)

    @property
    def current_time(self) -> Optional[datetime]:
        return self._pings[-1].timestamp if self._pings else None

    def ingest_ping(self, ping: AisPing) -> None:
        self._pings.append(ping)

    @property
    def source_mode(self) -> AisSourceMode:
        return AisSourceMode.LIVE_FEED

    @property
    def source_label(self) -> str:
        return self._source_label or f"Live AIS Feed ({self.endpoint_url})"

    def load(self) -> List[AisPing]:
        return list(self._pings)

    load_records = load


def get_default_source() -> AisSource:
    """Factory helper returning configured AIS data source."""
    return CsvReplaySource()


# Backwards compatibility helper
def get_default_adapter() -> AisSource:
    return get_default_source()
