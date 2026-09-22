from src.ais.schemas import EvidenceBundleV1


def validate_ais_integrity(m5_bundle: EvidenceBundleV1) -> None:
    """
    Validates that the AIS data provided by Module 5 hasn't been inappropriately altered.
    Throws ValueError if integrity constraints are violated.
    """
    # Check that reconstructed paths are explicitly marked as such.
    # Module 5/6 handles this, but M8 acts as a firewall.
    if hasattr(m5_bundle, "dark_path_hypotheses") and m5_bundle.dark_path_hypotheses:
        for hyp in m5_bundle.dark_path_hypotheses:
            if hyp.disclaimer != "HYPOTHESIS — reconstructed, not observed":
                # If a dark path hypothesis exists but claims it's not reconstructed, 
                # that's a data integrity violation.
                raise ValueError(
                    f"Vessel {m5_bundle.vessel_id} contains dark path data not marked as reconstructed."
                )

    # Note: No silent modification. If there's an AIS_GAP, it remains an AIS_GAP.
    # We do not attempt to fill it here.
