"""
Module 8 — Audit Linker

Links the Module 8 evidence chain to the cryptographic Merkle audit generated in Module 5.
"""

def generate_audit_reference(run_id: str) -> str:
    """
    Since Module 5 already has a Merkle audit ledger, Module 8 simply links to it.
    This prevents creating a duplicated, separate audit mechanism.
    """
    return f"urn:occuris:audit:merkle:{run_id}"
