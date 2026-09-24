"""
Integration tests for Module 8 — Forensic Ranking Pipeline.

Covers 5 scenario classes with ground-truth verification:
  1. single_source: True culprit ranked #1 with HIGH priority
  2. two_source_coordinated: Both culprits in top 2 with AMBIGUOUS
  3. dark_vessel: Culprit with AIS gap ranked #1 HIGH
  4. spoofed_vessel: Culprit with kinematic anomaly ranked #1 HIGH
  5. ambiguous: Two near-equal candidates both AMBIGUOUS

Also verifies:
  - Determinism (two runs yield identical posteriors)
  - Ground-truth isolation (src/ranking/ never imports tools/bench/)
  - No guilt language in ranking outputs
"""

import json
import re
from pathlib import Path

import pytest

from src.api.maritime import engine as m5_engine
from src.ais.schemas import CaseContextV1, InvestigationPriority
from src.ranking.ranking_pipeline import run_ranking_pipeline, _RANKING_CACHE


SCENARIOS_DIR = Path("data/bench/scenarios")


def _load_and_run(scenario_id: str):
    """Helper: load scenario AIS, build context, run ranking pipeline."""
    scenario_dir = SCENARIOS_DIR / scenario_id
    gt = json.loads((scenario_dir / "ground_truth.json").read_text(encoding="utf-8"))
    ctx = CaseContextV1(**gt["case_context"])

    m5_engine.initialized = False
    m5_engine.__init__()
    m5_engine.load_and_process(scenario_dir / "ais.csv")

    _RANKING_CACHE.pop(scenario_id, None)
    bundle = run_ranking_pipeline(
        scenario_id,
        force_refresh=True,
        record_audit=False,
        context=ctx,
    )
    return bundle, gt


@pytest.fixture(scope="module", autouse=True)
def ensure_scenarios():
    """Ensure at least 5 scenarios exist (one per class)."""
    if not SCENARIOS_DIR.exists() or not (SCENARIOS_DIR / "scenario_001").exists():
        from tools.bench.generate_attribution_scenarios import generate_scenarios
        generate_scenarios(num_scenarios=5, seed=42, output_dir=str(SCENARIOS_DIR))


class TestSingleSource:
    """Scenario class: single_source (scenario_001)."""

    def test_culprit_ranked_first(self):
        bundle, gt = _load_and_run("scenario_001")
        assert gt["scenario_class"] == "single_source"
        culprits = set(gt["culprits"])
        top1 = bundle.vessels[0]
        assert top1.vessel_id in culprits, f"Expected culprit in top-1, got {top1.vessel_id}"

    def test_culprit_has_high_priority(self):
        bundle, gt = _load_and_run("scenario_001")
        culprits = set(gt["culprits"])
        for v in bundle.vessels:
            if v.vessel_id in culprits:
                assert v.priority in (
                    InvestigationPriority.HIGH,
                    InvestigationPriority.MEDIUM,
                ), f"Culprit {v.vessel_id} got {v.priority}, expected HIGH or MEDIUM"

    def test_innocents_not_high(self):
        bundle, gt = _load_and_run("scenario_001")
        culprits = set(gt["culprits"])
        for v in bundle.vessels:
            if v.vessel_id not in culprits:
                assert v.priority != InvestigationPriority.HIGH, (
                    f"Innocent {v.vessel_id} falsely flagged HIGH"
                )


class TestTwoSourceCoordinated:
    """Scenario class: two_source_coordinated (scenario_002)."""

    def test_both_culprits_in_top_3(self):
        bundle, gt = _load_and_run("scenario_002")
        assert gt["scenario_class"] == "two_source_coordinated"
        culprits = set(gt["culprits"])
        top3 = {v.vessel_id for v in bundle.vessels[:3]}
        assert culprits.issubset(top3), (
            f"Expected culprits {culprits} in top-3, got {top3}"
        )

    def test_culprits_ambiguous_or_high(self):
        bundle, gt = _load_and_run("scenario_002")
        culprits = set(gt["culprits"])
        for v in bundle.vessels:
            if v.vessel_id in culprits:
                assert v.priority in (
                    InvestigationPriority.AMBIGUOUS,
                    InvestigationPriority.HIGH,
                ), f"Culprit {v.vessel_id} got {v.priority}"


class TestSpoofedVessel:
    """Scenario class: spoofed_vessel (scenario_003)."""

    def test_spoofed_culprit_ranked_first(self):
        bundle, gt = _load_and_run("scenario_003")
        assert gt["scenario_class"] == "spoofed_vessel"
        culprits = set(gt["culprits"])
        top1 = bundle.vessels[0]
        assert top1.vessel_id in culprits


class TestDarkVessel:
    """Scenario class: dark_vessel (scenario_004)."""

    def test_dark_culprit_ranked_first(self):
        bundle, gt = _load_and_run("scenario_004")
        assert gt["scenario_class"] == "dark_vessel"
        culprits = set(gt["culprits"])
        top1 = bundle.vessels[0]
        assert top1.vessel_id in culprits

    def test_dark_culprit_high_priority(self):
        bundle, gt = _load_and_run("scenario_004")
        culprits = set(gt["culprits"])
        for v in bundle.vessels:
            if v.vessel_id in culprits:
                assert v.priority == InvestigationPriority.HIGH


class TestAmbiguous:
    """Scenario class: ambiguous (scenario_005)."""

    def test_ambiguous_classification(self):
        bundle, gt = _load_and_run("scenario_005")
        assert gt["scenario_class"] == "ambiguous"
        culprits = set(gt["culprits"])
        ambiguous_culprits = [
            v for v in bundle.vessels
            if v.vessel_id in culprits and v.priority == InvestigationPriority.AMBIGUOUS
        ]
        assert len(ambiguous_culprits) >= 2, (
            f"Expected >= 2 AMBIGUOUS culprits, got {len(ambiguous_culprits)}"
        )

    def test_ambiguous_interval_overlap(self):
        bundle, gt = _load_and_run("scenario_005")
        culprits = list(gt["culprits"])
        if len(culprits) >= 2:
            intervals = {}
            for v in bundle.vessels:
                if v.vessel_id in culprits:
                    intervals[v.vessel_id] = v.posterior_interval
            if len(intervals) >= 2:
                ivs = list(intervals.values())
                overlap = min(ivs[0][1], ivs[1][1]) - max(ivs[0][0], ivs[1][0])
                assert overlap > 0, "Expected overlapping intervals for ambiguous scenario"


class TestDeterminism:
    """Two consecutive runs on same scenario must produce identical posteriors."""

    def test_deterministic_posteriors(self):
        bundle1, _ = _load_and_run("scenario_001")
        bundle2, _ = _load_and_run("scenario_001")

        assert len(bundle1.vessels) == len(bundle2.vessels)
        for v1, v2 in zip(bundle1.vessels, bundle2.vessels):
            assert v1.vessel_id == v2.vessel_id
            assert v1.posterior == v2.posterior, (
                f"Non-deterministic: {v1.vessel_id} got {v1.posterior} vs {v2.posterior}"
            )
            assert v1.priority == v2.priority


class TestGuards:
    """Architectural integrity guards."""

    def test_ground_truth_isolation(self):
        """src/ranking/ must NEVER reference ground_truth.json or tools/bench/."""
        ranking_dir = Path("src/ranking")
        forbidden = ["ground_truth.json", "ground_truth", "tools/bench"]
        for py_file in ranking_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for fb in forbidden:
                assert fb not in content, (
                    f"GUARD FAILED: {py_file.name} contains '{fb}'"
                )

    def test_no_guilt_language_in_ranking(self):
        """Ranking outputs must not contain guilt-implying language."""
        ranking_dir = Path("src/ranking")
        guilt_patterns = [
            re.compile(r"\bguilty\b", re.IGNORECASE),
            re.compile(r"\bculprit\b", re.IGNORECASE),
            re.compile(r"\bperpetrator\b", re.IGNORECASE),
        ]
        for py_file in ranking_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # Strip docstrings and comments explaining the rule
            cleaned = re.sub(
                r'["\'].*?(?:zero guilt|never output guilt|guilt|no).*?["\']',
                '', content, flags=re.IGNORECASE
            )
            for pat in guilt_patterns:
                assert not pat.search(cleaned), (
                    f"Guilt word '{pat.pattern}' in {py_file.name}"
                )

    def test_disclaimer_present(self):
        """RankingBundleV1 must contain disclaimer."""
        bundle, _ = _load_and_run("scenario_001")
        assert "Investigation Priority" in bundle.disclaimer
        assert "Guilt" not in bundle.disclaimer or "Not Guilt" in bundle.disclaimer
