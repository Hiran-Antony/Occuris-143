"""
Module 8 — Data Provenance Tracking

Captures the source, timestamp, and versioning of datasets used in the investigation.
Explicitly flags synthetic test data to ensure it is never passed off as real-world evidence.
"""

from typing import Any, Dict

from src.investigation.schemas import DataProvenance


def build_provenance_record(
    case_cfg: Dict[str, Any],
    environment_version: str,
) -> DataProvenance:
    """
    Constructs the data provenance record.
    For the MVP, since we are using synthetic/test data, this explicitly flags it.
    """
    
    # In a live integration, these would be extracted from the actual Sentinel-1,
    # Copernicus, and AIS metadata files.
    is_synthetic = case_cfg.get("is_synthetic", True)
    
    sar_dataset = {
        "source": "Sentinel-1 (Simulated/Test)" if is_synthetic else "Sentinel-1",
        "dataset_id": case_cfg["id"],
        "processing_version": "Occuris_MVP_v1"
    }
    
    ais_dataset = {
        "source": "AIS_TEST_PROVIDER" if is_synthetic else "AIS_PROVIDER",
        "position_source": "MIXED (OBSERVED/RECONSTRUCTED)",
    }
    
    env_dataset = {
        "source": "Copernicus Marine (Simulated/Test)" if is_synthetic else "Copernicus Marine",
        "version": environment_version
    }
    
    disclaimer = (
        "WARNING: This investigation relies on synthetic or test datasets. "
        "It must not be used as actual forensic evidence."
    ) if is_synthetic else None
    
    return DataProvenance(
        sar_dataset=sar_dataset,
        ais_dataset=ais_dataset,
        environment_dataset=env_dataset,
        is_synthetic=is_synthetic,
        synthetic_disclaimer=disclaimer
    )
