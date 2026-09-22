"""
Module 8 — Evidence Graph Generator

Generates a node-and-edge graph of the evidence chain for dashboard visualization.
"""

from typing import Any, Dict, List

from src.investigation.schemas import InvestigationReportBundleV1


def build_evidence_graph(bundle: InvestigationReportBundleV1) -> Dict[str, Any]:
    """
    Constructs a JSON-serializable graph for the SIH Dashboard.
    """
    nodes = []
    edges = []
    
    # 1. SAR Node
    nodes.append({
        "id": "sar",
        "label": "SAR IMAGE",
        "type": "observation",
        "data": bundle.sar_observation
    })
    
    # 2. Spill Detection
    nodes.append({
        "id": "spill",
        "label": "SPILL DETECTION",
        "type": "geometry"
    })
    edges.append({"source": "sar", "target": "spill"})
    
    # 3. Source Zone
    nodes.append({
        "id": "source_zone",
        "label": "SOURCE ZONE",
        "type": "analysis",
        "data": bundle.source_zone
    })
    edges.append({"source": "spill", "target": "source_zone"})
    
    # 4. Candidates
    for cand in bundle.candidate_vessels:
        vid = cand.vessel_id
        
        # Vessel Node
        nodes.append({
            "id": f"vessel_{vid}",
            "label": f"VESSEL {vid}",
            "type": "vessel",
            "status": cand.status.value
        })
        edges.append({"source": "source_zone", "target": f"vessel_{vid}"})
        
        # AIS Node
        nodes.append({
            "id": f"ais_{vid}",
            "label": "AIS DATA",
            "type": "data",
            "data": {"status": cand.ais_evidence.ais_status}
        })
        edges.append({"source": f"vessel_{vid}", "target": f"ais_{vid}"})
        
        # M6 Node
        nodes.append({
            "id": f"m6_{vid}",
            "label": "MODULE 6",
            "type": "analysis",
            "data": {
                "spatial": cand.spatial_evidence.__dict__,
                "temporal": cand.temporal_evidence.__dict__
            }
        })
        edges.append({"source": f"ais_{vid}", "target": f"m6_{vid}"})
        
        # Counterfactual Node
        nodes.append({
            "id": f"m7_{vid}",
            "label": "COUNTERFACTUAL",
            "type": "simulation"
        })
        edges.append({"source": f"m6_{vid}", "target": f"m7_{vid}"})
        
        # Physical Match Node
        match_data = cand.physical_evidence.__dict__ if cand.physical_evidence else {}
        nodes.append({
            "id": f"match_{vid}",
            "label": "PHYSICAL MATCH",
            "type": "evidence",
            "data": match_data
        })
        edges.append({"source": f"m7_{vid}", "target": f"match_{vid}"})
        
    return {
        "nodes": nodes,
        "edges": edges
    }
