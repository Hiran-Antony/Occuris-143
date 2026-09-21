"""Integrity and architectural guard tests."""

import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
AIS_DIR = ROOT / "src" / "ais"
API_MARITIME = ROOT / "src" / "api" / "maritime.py"


def test_guard_zero_guilt_language():
    """Module 5 must never use guilt language (e.g. culprit, guilty, smuggler)."""
    guilt_patterns = [
        re.compile(r"\bculprit\b", re.IGNORECASE),
        re.compile(r"\bguilty\b", re.IGNORECASE),
        re.compile(r"\bsmuggler\b", re.IGNORECASE),
        re.compile(r"\bsmuggling\b", re.IGNORECASE),
        re.compile(r"\bperpetrator\b", re.IGNORECASE),
    ]

    for py_file in AIS_DIR.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pat in guilt_patterns:
            matches = pat.findall(content)
            # Allow docstrings explaining that zero guilt language is used
            cleaned_content = re.sub(r'["\'].*?(?:zero guilt|no).*?["\']', '', content, flags=re.IGNORECASE)
            assert not pat.search(cleaned_content), f"Guilt word '{pat.pattern}' found in {py_file.name}"


def test_guard_no_drift_or_scoring_imports():
    """Module 5 must not import drift modeling, weathering, or attribution scoring."""
    prohibited_modules = [
        "src.drift",
        "src.detection",
        "parcels",
        "sklearn.linear_model",
    ]

    for py_file in AIS_DIR.glob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line_clean = line.strip()
            if line_clean.startswith("import ") or line_clean.startswith("from "):
                for prohibited in prohibited_modules:
                    assert prohibited not in line_clean, (
                        f"Prohibited import '{prohibited}' in {py_file.name}: {line_clean}"
                    )
