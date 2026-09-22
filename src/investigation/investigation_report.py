"""
Module 8 — Investigation Report Generator

Generates a human-readable OCCURIS INVESTIGATION REPORT from the evidence bundle.
"""

from src.investigation.schemas import InvestigationReportBundleV1


def generate_report_text(bundle: InvestigationReportBundleV1) -> str:
    """
    Produces the formatted text report.
    """
    lines = []
    lines.append("OCCURIS INVESTIGATION REPORT")
    lines.append("────────────────────────────")
    lines.append(f"Incident ID: {bundle.incident_id}")
    lines.append(f"Generated:   {bundle.generated_at}")
    lines.append("")
    
    # 1. Incident
    lines.append("Incident")
    lines.append("---------")
    sar = bundle.sar_observation
    lines.append(f"SAR acquisition: {sar.get('acquisition_time_iso', 'UNKNOWN')} UTC")
    lines.append(f"Detection:       {sar.get('detection_type', 'Possible oil-like surface anomaly')}")
    lines.append("")
    
    # 2. Source Analysis
    lines.append("Source analysis")
    lines.append("---------------")
    sz = bundle.source_zone
    rw = bundle.release_window
    lines.append(
        f"Estimated source zone: Center ({sz.get('lat', 'N/A')}, {sz.get('lon', 'N/A')})"
    )
    lines.append(
        f"Estimated release window: {rw.get('start_iso', 'N/A')} to {rw.get('end_iso', 'N/A')} UTC"
    )
    lines.append("")
    
    # 3. Candidates
    lines.append("Candidate vessels")
    lines.append("-----------------")
    for cand in bundle.candidate_vessels:
        lines.append(f"Vessel {cand.vessel_id}")
        spat_overlap = "YES" if cand.spatial_evidence.intersects_origin_zone else "NO"
        lines.append(f"Spatial overlap: {spat_overlap}")
        
        temp_enum = cand.temporal_evidence.overlap_status.value
        temp_overlap = "YES" if "PARTIAL" not in temp_enum and "NO" not in temp_enum else (
            "PARTIAL" if "PARTIAL" in temp_enum else "NO"
        )
        lines.append(f"Temporal overlap: {temp_overlap}")
        
        lines.append(f"AIS status: {cand.ais_evidence.ais_status}")
        lines.append(f"Physical consistency: {cand.status.value}")
        lines.append("")
        
    # 4. Conclusion
    lines.append("Conclusion")
    lines.append("----------")
    lines.append(
        "The available evidence identifies the hypotheses that are\n"
        "physically consistent with the observed spill and those that\n"
        "are contradicted or unresolved."
    )
    lines.append("")
    for limitation in bundle.limitations:
        lines.append(limitation)
    lines.append("")
    
    if bundle.data_provenance.synthetic_disclaimer:
        lines.append("DISCLAIMER:")
        lines.append(bundle.data_provenance.synthetic_disclaimer)
        lines.append("")

    lines.append(f"Audit Ledger Ref: {bundle.audit_ledger_reference}")
        
    return "\n".join(lines)
