"""
Generates m5_tracks.json and m5_events.json from the actual AIS CSV dataset
using the real Module 5 pipeline (CsvReplaySource → TrackBuilder → CrossingDetector
→ MaritimeMemory → DelayAnalyzer).

No coordinates, timestamps, speeds, or crossing events are fabricated.
All data is derived directly from the AIS CSV and gateway configuration.
"""
import json
from pathlib import Path

# Set up PYTHONPATH
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ais.ingest import CsvReplaySource
from src.ais.track_builder import TrackBuilder
from src.ais.crossing import CrossingDetector
from src.ais.maritime_memory import MaritimeMemory
from src.ais.delay_analysis import DelayAnalyzer
from src.config import ROOT


def main():
    print("=== M5 Data Generation ===")

    # ── Ingest raw AIS ────────────────────────────────────────────────────
    print("Loading AIS CSV...")
    source = CsvReplaySource(ROOT / 'data/raw/ais/ais_sample.csv')
    pings = source.load()
    print(f"  {len(pings)} pings loaded.")

    # ── Build per-vessel tracks (including gap detection) ─────────────────
    print("Building tracks...")
    tb = TrackBuilder()
    tracks = tb.build_tracks(pings)
    print(f"  {len(tracks)} tracks built.")

    # ── Detect gateway crossings ──────────────────────────────────────────
    print("Detecting gateway crossings...")
    detector = CrossingDetector()
    crossing_events = detector.detect_crossings(tracks)
    print(f"  {len(crossing_events)} crossing events detected.")

    # ── Build vessel journeys and delay analysis ───────────────────────────
    print("Building journeys & delay analysis...")
    mm = MaritimeMemory()
    journeys = mm.build_journeys(tracks, crossing_events)
    delay_analyzer = DelayAnalyzer()
    delay_analyzer.analyze_all(journeys)
    print(f"  {len(journeys)} journeys built.")

    # ── Serialize m5_tracks.json ──────────────────────────────────────────
    # Each vessel entry contains:
    #   - vessel_id, vessel_name, mmsi
    #   - positions: list of observed AIS pings (lat, lon, timestamp, sog, cog, nav_status)
    #   - gaps: list of detected reporting gaps (start_lat/lon, end_lat/lon, gap_start, gap_end, duration_minutes)
    print("Serializing m5_tracks.json...")
    tracks_out = []
    for vessel_id, track in tracks.items():
        j = journeys.get(vessel_id)
        tracks_out.append({
            "vessel_id": vessel_id,
            "vessel_name": track.vessel_name,
            "mmsi": track.mmsi,
            "total_distance_km": track.total_distance_km,
            "journey": {
                "entry_gateway": j.entry_gateway if j else None,
                "exit_gateway": j.exit_gateway if j else None,
                "actual_duration_hours": j.actual_duration_h if j else None,
                "expected_duration_hours": j.expected_duration_h if j else None,
                "delay_hours": j.delay_h if j else None,
                "status": j.status.value if j else None,
                "expected_basis": j.expected_basis.value if j else None,
            } if j else None,
            # Actual observed AIS positions — these are read directly from the CSV
            "positions": [
                {
                    "timestamp": p.timestamp.isoformat(),
                    "lat": p.lat,
                    "lon": p.lon,
                    "sog": p.sog,
                    "cog": p.cog,
                    "nav_status": p.nav_status,
                    "physically_impossible": p.physically_impossible,
                }
                for p in track.pings
            ],
            # AIS gaps detected by Module 5 TrackBuilder
            "gaps": [
                {
                    "gap_start": g.gap_start.isoformat(),
                    "gap_end": g.gap_end.isoformat(),
                    "duration_minutes": g.duration_minutes,
                    "start_lat": g.start_lat,
                    "start_lon": g.start_lon,
                    "end_lat": g.end_lat,
                    "end_lon": g.end_lon,
                    "implied_speed_knots": g.implied_speed_knots,
                }
                for g in track.gaps
            ],
        })

    m5_tracks_path = ROOT / 'data/processed/m5_tracks.json'
    with open(m5_tracks_path, 'w', encoding='utf-8') as f:
        json.dump(tracks_out, f, indent=2)
    print(f"  Saved {len(tracks_out)} tracks → {m5_tracks_path}")

    # ── Serialize m5_events.json ──────────────────────────────────────────
    # Each entry is a GatewayCrossingEvent produced by the M5 CrossingDetector
    print("Serializing m5_events.json...")
    events_out = []
    for ev in crossing_events:
        events_out.append({
            "event_id": ev.event_id,
            "vessel_id": ev.vessel_id,
            "vessel_name": ev.vessel_name,
            "gateway_id": ev.gateway_id,
            "event_type": ev.event_type.value,   # "ENTRY" | "EXIT" | "CORRIDOR_CROSSING"
            "timestamp": ev.timestamp.isoformat(),
            "latitude": ev.latitude,
            "longitude": ev.longitude,
            "speed_knots": ev.speed_knots,
            "course_deg": ev.course_deg,
            "interpolation_ratio": ev.interpolation_ratio,
            "source": ev.source,
        })

    m5_events_path = ROOT / 'data/processed/m5_events.json'
    with open(m5_events_path, 'w', encoding='utf-8') as f:
        json.dump(events_out, f, indent=2)
    print(f"  Saved {len(events_out)} crossing events → {m5_events_path}")

    # ── Serialize m5_vessels.json (vessel summary) ────────────────────────
    print("Serializing m5_vessels.json...")
    vessels_out = []
    for vessel_id, track in tracks.items():
        j = journeys.get(vessel_id)
        has_gap = len(track.gaps) > 0
        # Count events per vessel
        v_events = [e for e in crossing_events if e.vessel_id == vessel_id]
        vessels_out.append({
            "mmsi": str(track.mmsi),
            "vessel_id": vessel_id,
            "name": track.vessel_name or f"Unknown {vessel_id}",
            "vessel_type": "tanker" if "TANKER" in (track.vessel_name or "").upper() else "cargo",
            "ais_continuity": "GAP_DETECTED" if has_gap else "CONTINUOUS",
            "journey": {
                "entry_gateway": j.entry_gateway if j else None,
                "exit_gateway": j.exit_gateway if j else None,
                "actual_duration_hours": j.actual_duration_h if j else None,
                "expected_duration_hours": j.expected_duration_h if j else None,
                "delay_hours": j.delay_h if j else None,
                "status": j.status.value if j else None,
                "expected_basis": j.expected_basis.value if j else None,
            } if j else None,
            "behaviour_event_count": len(v_events),
            "unexplained_event_count": 0,  # M6 classification; placeholder until M6 run
        })

    m5_vessels_path = ROOT / 'data/processed/m5_vessels.json'
    with open(m5_vessels_path, 'w', encoding='utf-8') as f:
        json.dump(vessels_out, f, indent=2)
    print(f"  Saved {len(vessels_out)} vessels → {m5_vessels_path}")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n=== Summary ===")
    all_ts = [p.timestamp for track in tracks.values() for p in track.pings]
    if all_ts:
        print(f"  AIS range: {min(all_ts).isoformat()} → {max(all_ts).isoformat()}")
    for vessel_id, track in tracks.items():
        j = journeys.get(vessel_id)
        n_gaps = len(track.gaps)
        n_ev = len([e for e in crossing_events if e.vessel_id == vessel_id])
        print(f"  {vessel_id} ({track.vessel_name}): {len(track.pings)} pings, {n_gaps} gaps, {n_ev} crossings")


if __name__ == '__main__':
    main()
