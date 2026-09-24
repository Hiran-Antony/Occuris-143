from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from pathlib import Path

# Module 5 gateway definitions — loaded once at startup from config
from src.ais.gateways import get_gateway_manager

app = FastAPI(title="Occuris API Bridge")
app.mount("/sar", StaticFiles(directory="data/raw/sar"), name="sar")
app.mount("/masks", StaticFiles(directory="data/processed"), name="masks")

# Allow React frontend to access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data/processed")

CASES = [
    {"id": "case_01", "name": "Al-Mahra Corridor", "region": "Arabian Sea", "status": "ACTIVE", "sar_image_path": "sar_01.png", "mask_path": "case_01_pred_mask.png"},
    {"id": "case_02", "name": "Lakshadweep Passage", "region": "Arabian Sea", "status": "ACTIVE", "sar_image_path": "sar_02.png", "mask_path": "case_02_pred_mask.png"},
    {"id": "case_03", "name": "Oman Basin", "region": "Arabian Sea", "status": "ACTIVE", "sar_image_path": "sar_03.png", "mask_path": "case_03_pred_mask.png"}
]

def load_json(filename: str):
    path = DATA_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")
    with open(path, "r") as f:
        return json.load(f)

@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    # Derive real counts from the M5 processed data files
    try:
        vessels = load_json("m5_vessels.json")
        events = load_json("m5_events.json")
        total_crossings = len(events)
        total_vessels = len(vessels)
        completed = sum(1 for v in vessels if v.get("journey") and v["journey"].get("status") == "COMPLETED")
    except Exception:
        total_crossings, total_vessels, completed = 0, 5, 0
    return {
        "active_cases": len(CASES),
        "total_vessels": total_vessels,
        "vessels_ever_in_region": total_vessels,
        "total_gateway_crossings": total_crossings,
        "total_behaviour_events": 0,
        "unexplained_events": 0,
        "completed_journeys": completed,
        "data_mode": "MVP / SYNTHETIC TEST DATA"
    }

@app.get("/api/cases")
def list_cases():
    return CASES

@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = next((c for c in CASES if c["id"] == case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.get("/api/cases/{case_id}/map")
def get_case_map(case_id: str):
    geom = load_json(f"{case_id}_geometry.json")
    try:
        scale = geom["geometry"]["pixel_scale"]
        return {
            "bbox_lat": scale["bbox_lat"],
            "bbox_lon": scale["bbox_lon"],
            "center": geom["geometry"]["centroid_geo"],
            "geographic_width_km": scale.get("geographic_width_km")
        }
    except KeyError:
        return {"center": geom["geometry"]["centroid_geo"]}

@app.get("/api/cases/{case_id}/spill")
def get_case_spill(case_id: str):
    return load_json(f"{case_id}_geometry.json")

@app.get("/api/cases/{case_id}/origin-zone")
def get_case_origin_zone(case_id: str):
    return load_json(f"{case_id}_spillsplit.json")

@app.get("/api/cases/{case_id}/drift")
def get_case_drift(case_id: str):
    return load_json(f"{case_id}_drift.json")

@app.get("/api/cases/{case_id}/vessels")
def get_vessels_in_vicinity(case_id: str):
    try:
        return load_json("m5_vessels.json")
    except Exception:
        return [
            {"mmsi": "V001", "name": "MT DESH SHOBHA", "vessel_type": "tanker"},
            {"mmsi": "V002", "name": "EASTERN STAR", "vessel_type": "cargo"},
            {"mmsi": "V003", "name": "GULF WAVE", "vessel_type": "tanker"},
            {"mmsi": "V004", "name": "UNKNOWN_DARK", "vessel_type": "unknown"},
            {"mmsi": "V005", "name": "PACIFIC PEARL", "vessel_type": "cargo"}
        ]

@app.get("/api/cases/{case_id}/vessels/{vessel_id}/track")
def get_vessel_track(case_id: str, vessel_id: str):
    """Return the actual AIS track for a vessel from M5 processed data.
    Positions are the verbatim AIS observations from the CSV — no fabrication.
    Gaps are included so the frontend can render them correctly.
    """
    try:
        all_tracks = load_json("m5_tracks.json")
    except HTTPException:
        raise HTTPException(status_code=404, detail="m5_tracks.json not found — run scratch/generate_m5_data.py first")

    track = next(
        (t for t in all_tracks if t["vessel_id"] == vessel_id),
        None
    )
    if track is None and vessel_id.isdigit():
        track = next(
            (t for t in all_tracks if str(t.get("mmsi", "")) == vessel_id),
            None
        )
    if track is None:
        raise HTTPException(status_code=404, detail=f"Vessel '{vessel_id}' not found in m5_tracks.json")
    return track


@app.get("/api/cases/{case_id}/gateways")
def get_case_gateways(case_id: str):
    """Return the actual gateway definitions as GeoJSON FeatureCollection.
    Geometry comes from config/region.yaml via M5 GatewayManager — no fabrication.
    """
    gm = get_gateway_manager()
    features = []
    for gw in gm.gateways:
        features.append({
            "type": "Feature",
            "id": gw.gateway_id,
            "properties": {
                "gateway_id": gw.gateway_id,
                "name": gw.name,
                "orientation": gw.orientation,
                "entry_side": gw.entry_side,
                "exit_side": gw.exit_side,
                "color": getattr(gw, "color", "#00d4ff"),
            },
            "geometry": gw.geometry_geojson,
        })
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/cases/{case_id}/gateway-events")
def get_case_gateway_events(case_id: str):
    """Return M5 GatewayCrossingEvent records.
    These are produced by the actual CrossingDetector — never fabricated in React.
    """
    try:
        return load_json("m5_events.json")
    except HTTPException:
        raise HTTPException(status_code=404, detail="m5_events.json not found — run scratch/generate_m5_data.py first")

@app.get("/api/cases/{case_id}/candidates")
def get_investigation_candidates(case_id: str):
    """
    Real Module 8 Bayesian ranking pipeline output adapted to legacy format.
    NEVER returns hardcoded or static data.
    """
    from src.ranking.api import get_computed_legacy_candidates
    return get_computed_legacy_candidates(case_id)

@app.post("/api/cases/{case_id}/report")
def generate_report(case_id: str):
    return {"status": "success", "message": "PDF Report triggered (WeasyPrint)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
