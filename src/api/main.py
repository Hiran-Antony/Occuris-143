from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from pathlib import Path

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
    return {
        "active_cases": len(CASES),
        "total_vessels": 5,
        "vessels_ever_in_region": 5,
        "total_gateway_crossings": 20,
        "total_behaviour_events": 12,
        "unexplained_events": 3,
        "completed_journeys": 4,
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

# Synthetic Vessel APIs for Maritime Memory
MOCK_VESSELS = [
    {"mmsi": "V001", "name": "MT DESH SHOBHA", "vessel_type": "tanker"},
    {"mmsi": "V002", "name": "EASTERN STAR", "vessel_type": "cargo"},
    {"mmsi": "V003", "name": "GULF WAVE", "vessel_type": "tanker"},
    {"mmsi": "V004", "name": "UNKNOWN_DARK", "vessel_type": "unknown"},
    {"mmsi": "V005", "name": "PACIFIC PEARL", "vessel_type": "cargo"}
]

@app.get("/api/cases/{case_id}/vessels")
def get_vessels_in_vicinity(case_id: str):
    return MOCK_VESSELS

@app.get("/api/cases/{case_id}/vessels/{vessel_id}/track")
def get_vessel_track(case_id: str, vessel_id: str):
    # We will just return a mock track centered around the case centroid for now, 
    # since we don't have static track files dumped.
    # In a real implementation this would fetch from the M5 DB.
    geom = load_json(f"{case_id}_geometry.json")
    lat = geom["geometry"]["centroid_geo"]["latitude"]
    lon = geom["geometry"]["centroid_geo"]["longitude"]
    
    return {
        "mmsi": vessel_id,
        "positions": [
            {"timestamp": "2024-03-15T00:00:00Z", "latitude": lat - 1, "longitude": lon - 1, "speed": 12.0, "course": 45},
            {"timestamp": "2024-03-15T06:00:00Z", "latitude": lat, "longitude": lon, "speed": 12.5, "course": 45},
            {"timestamp": "2024-03-15T12:00:00Z", "latitude": lat + 1, "longitude": lon + 1, "speed": 12.1, "course": 45}
        ]
    }

@app.get("/api/cases/{case_id}/candidates")
def get_investigation_candidates(case_id: str):
    # This represents the M6-M8 evidence bundles pass-through.
    # Since they weren't saved to disk, we construct a strict representation 
    # of the CandidateEvidence schema dynamically for the UI.
    
    geom = load_json(f"{case_id}_geometry.json")
    
    return [
        {
            "vessel_id": "V004",
            "spatial_evidence": {
                "intersects_origin_zone": True,
                "minimum_distance_to_origin_zone_km": 1.2
            },
            "temporal_evidence": {
                "overlap_status": "TEMPORAL_OVERLAP",
                "overlap_minutes": 140
            },
            "ais_evidence": {
                "ais_status": "AIS_GAP_DARK"
            },
            "physical_evidence": {
                "iou": 0.42,
                "centroid_distance_km": 4.1,
                "area_similarity": 0.81
            },
            "status": "PARTIALLY_SUPPORTED",
            "contradicting_evidence": []
        }
    ]

@app.post("/api/cases/{case_id}/report")
def generate_report(case_id: str):
    return {"status": "success", "message": "PDF Report triggered (WeasyPrint)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
