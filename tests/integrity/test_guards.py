"""Integrity and architectural guard tests."""

import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
AIS_DIR = ROOT / "src" / "ais"
VERIF_DIR = ROOT / "src" / "verification"
API_MARITIME = ROOT / "src" / "api" / "maritime.py"


def test_guard_zero_guilt_language():
    """Modules 5 & 6 must never use guilt language (e.g. culprit, guilty, smuggler)."""
    guilt_patterns = [
        re.compile(r"\bculprit\b", re.IGNORECASE),
        re.compile(r"\bguilty\b", re.IGNORECASE),
        re.compile(r"\bsmuggler\b", re.IGNORECASE),
        re.compile(r"\bsmuggling\b", re.IGNORECASE),
        re.compile(r"\bperpetrator\b", re.IGNORECASE),
    ]

    target_files = list(AIS_DIR.glob("*.py")) + list(VERIF_DIR.glob("*.py"))
    for py_file in target_files:
        content = py_file.read_text(encoding="utf-8")
        # Allow docstrings explaining that zero guilt language is used
        cleaned_content = re.sub(r'["\'].*?(?:zero guilt|never output guilt|never outputs guilt|guilt|no).*?["\']', '', content, flags=re.IGNORECASE)
        for pat in guilt_patterns:
            assert not pat.search(cleaned_content), f"Guilt word '{pat.pattern}' found in {py_file.name}"


def test_guard_no_drift_or_scoring_imports():
    """Modules 5 & 6 must not import drift modeling, weathering, or attribution scoring."""
    prohibited_modules = [
        "src.drift",
        "src.attribution",
        "src.detection",
        "parcels",
        "sklearn.linear_model",
    ]

    target_files = list(AIS_DIR.glob("*.py")) + list(VERIF_DIR.glob("*.py"))
    for py_file in target_files:
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line_clean = line.strip()
            if line_clean.startswith("import ") or line_clean.startswith("from "):
                for prohibited in prohibited_modules:
                    assert prohibited not in line_clean, (
                        f"Prohibited import '{prohibited}' in {py_file.name}: {line_clean}"
                    )


RANKING_DIR = ROOT / "src" / "ranking"


def test_guard_ground_truth_isolation():
    """src/ranking/ must NEVER reference ground_truth.json or tools/bench/."""
    forbidden = ["ground_truth.json", "ground_truth", "tools/bench"]
    for py_file in RANKING_DIR.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for fb in forbidden:
            assert fb not in content, (
                f"GUARD FAILED: {py_file.name} references '{fb}' — "
                f"production code must never access benchmark ground truth"
            )


def test_guard_ranking_no_guilt_language():
    """src/ranking/ must never use guilt-implying language."""
    guilt_patterns = [
        re.compile(r"\bguilty\b", re.IGNORECASE),
        re.compile(r"\bculprit\b", re.IGNORECASE),
        re.compile(r"\bperpetrator\b", re.IGNORECASE),
    ]
    for py_file in RANKING_DIR.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        cleaned = re.sub(
            r'["\'].*?(?:zero guilt|never output guilt|Investigation Priority|Not Guilt|guilt|no).*?["\']',
            '', content, flags=re.IGNORECASE
        )
        for pat in guilt_patterns:
            assert not pat.search(cleaned), (
                f"Guilt word '{pat.pattern}' found in {py_file.name}"
            )
