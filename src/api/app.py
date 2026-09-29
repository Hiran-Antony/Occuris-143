"""
Occuris MVP — FastAPI Application Server
Integrates AI Detection, Drift Simulation, and Module 5 Maritime Memory & Virtual Gateways.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.maritime import ensure_pipeline, router as maritime_v1_router
from src.api.maritime_router import router as maritime_compat_router, state as maritime_compat_state
from src.api.verification import router as verification_v1_router
from src.ranking.api import router as ranking_v1_router, compat_router as ranking_compat_router
from src.config import ROOT

app = FastAPI(
    title="OCCURIS Maritime Intelligence API",
    description="Module 5: Maritime Memory, Virtual Gateways, Behavioral DNA, and Merkle Audit; Module 6: AIS Verification; Module 8: Forensic Ranking",
    version="1.0.0",
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount official /api/v1 routers
app.include_router(maritime_v1_router)
app.include_router(verification_v1_router)
app.include_router(ranking_v1_router)

# Mount legacy /api router for backwards compatibility
app.include_router(maritime_compat_router)
app.include_router(ranking_compat_router)


@app.on_event("startup")
def on_startup():
    """Warm up and initialize Module 5 pipeline on boot."""
    print("[OCCURIS] Booting Module 5 Maritime Memory & Virtual Gateway pipeline...")
    ensure_pipeline()
    maritime_compat_state.initialize()
    print("[OCCURIS] Pipeline initialized successfully.")


@app.get("/api/health")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "OCCURIS Maritime Intelligence",
        "version": "1.0.0",
        "module_5": "active",
    }


@app.post("/api/cases/{case_id}/report")
@app.post("/api/v1/cases/{case_id}/report")
def generate_report(case_id: str):
    """Trigger report generation and store deterministic dossier hash."""
    from src.api.reports import gather_case_dossier_data
    dossier = gather_case_dossier_data(case_id)
    return {
        "status": "success",
        "case_id": case_id,
        "dossier_sha256": dossier["dossier_sha256"],
        "pdf_url": f"/api/cases/{case_id}/report/pdf",
        "message": "Forensic MARPOL Annex I report generated deterministically",
    }


@app.get("/api/cases/{case_id}/report/pdf")
@app.get("/api/v1/cases/{case_id}/report/pdf")
def get_report_pdf(case_id: str):
    """Download court-ready forensic PDF report."""
    from fastapi.responses import Response
    from datetime import datetime, timezone
    from src.api.reports import generate_report_pdf

    pdf_bytes = generate_report_pdf(case_id)
    filename = f"Occuris_Case_{case_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Mount frontend static files
frontend_dir = ROOT / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
