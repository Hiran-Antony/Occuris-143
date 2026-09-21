"""Unit tests for src/ais/ingest.py."""

import io
from datetime import datetime, timezone
from pathlib import Path
import pytest

from src.ais.ingest import CsvReplaySource, LiveFeedSource, get_default_source
from src.ais.schemas import AisSourceMode, AisPing


def test_csv_replay_source_load(tmp_path: Path):
    csv_file = tmp_path / "test_ais.csv"
    csv_file.write_text(
        "mmsi,vessel_id,vessel_name,timestamp,lat,lon,sog,cog,nav_status,source\n"
        "123456789,V001,TEST_SHIP,2024-03-15T00:00:00Z,18.5,65.0,12.0,180.0,0,AIS_CLASS_A\n"
        "123456789,V001,TEST_SHIP,2024-03-15T00:10:00Z,18.3,65.0,12.0,180.0,0,AIS_CLASS_A\n"
    )

    source = CsvReplaySource(csv_path=csv_file)
    records = source.load_records()

    assert len(records) == 2
    assert source.total_pings == 2
    assert records[0].vessel_id == "V001"
    assert records[0].lat == 18.5
    assert records[0].lon == 65.0
    assert records[0].sog == 12.0
    assert records[0].cog == 180.0
    assert source.source_mode == AisSourceMode.SYNTHETIC_REPLAY
    assert source.is_live is False


def test_csv_replay_source_missing_file():
    source = CsvReplaySource(csv_path=Path("non_existent_file.csv"))
    records = source.load_records()
    assert records == []
    assert source.total_pings == 0


def test_live_feed_source():
    live = LiveFeedSource(source_label="TEST_FEED")
    assert live.source_mode == AisSourceMode.LIVE_FEED
    assert live.is_live is True
    assert live.total_pings == 0
    assert live.current_time is None

    ping = AisPing(
        mmsi=987654321,
        vessel_id="V_LIVE",
        vessel_name="LIVE VESSEL",
        timestamp=datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
        lat=15.0,
        lon=65.0,
        sog=14.0,
        cog=90.0,
        nav_status=0,
    )
    live.ingest_ping(ping)
    assert live.total_pings == 1
    assert live.current_time == ping.timestamp
    assert len(live.load_records()) == 1


def test_get_default_source():
    src = get_default_source()
    assert src.source_mode == AisSourceMode.SYNTHETIC_REPLAY
