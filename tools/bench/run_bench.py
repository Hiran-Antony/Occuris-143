"""
OccurisBench — Benchmark Runner (§10)

Evaluates Module 8 ranking pipeline against ground-truth scenarios.
Fits Platt calibration on calib split, evaluates on eval split.

Metrics:
  - Top-1 Accuracy: True culprit ranked #1
  - Top-3 Coverage: True culprit in top 3
  - IVFF: Innocent Vessel False-Flag Rate (innocent vessels ranked HIGH)
  - ECE: Expected Calibration Error

Usage:
  python tools/bench/run_bench.py --scenarios data/bench/scenarios --split calib:90,eval:210
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Resolve project root for imports
_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BENCH_ROOT))

from tools.bench.calibration import apply_platt_scaling, compute_ece, fit_platt_scaling


def _config_hash() -> str:
    """SHA-256 of config/ranking.yaml for provenance."""
    config_path = _BENCH_ROOT / "config" / "ranking.yaml"
    if config_path.exists():
        return hashlib.sha256(config_path.read_bytes()).hexdigest()[:16]
    return "unknown"


def _code_revision() -> str:
    """Get short git revision if available."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=str(_BENCH_ROOT),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _ground_truth_isolation_check() -> bool:
    """
    Guard test: verify src/ranking/ never imports or reads ground_truth.json.
    Scans all .py files in src/ranking/ for forbidden references.
    """
    ranking_dir = _BENCH_ROOT / "src" / "ranking"
    forbidden = ["ground_truth.json", "ground_truth", "tools/bench"]
    for py_file in ranking_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for fb in forbidden:
            if fb in content:
                return False
    return True


def run_single_scenario(
    scenario_dir: Path,
) -> Dict[str, Any]:
    """
    Run ranking pipeline on a single scenario.
    Returns dict with results and ground truth for aggregation.
    """
    from src.api.maritime import engine as m5_engine
    from src.ais.schemas import CaseContextV1
    from src.ranking.ranking_pipeline import run_ranking_pipeline, _RANKING_CACHE

    gt_path = scenario_dir / "ground_truth.json"
    ais_path = scenario_dir / "ais.csv"

    if not gt_path.exists() or not ais_path.exists():
        return {"error": f"Missing files in {scenario_dir}"}

    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    scenario_id = gt["scenario_id"]
    scenario_class = gt["scenario_class"]
    culprits = set(gt["culprits"])

    # Build context from ground truth
    ctx = CaseContextV1(**gt["case_context"])

    # Load AIS data and run pipeline
    m5_engine.initialized = False
    m5_engine.__init__()
    m5_engine.load_and_process(ais_path)

    # Clear cache for this scenario
    _RANKING_CACHE.pop(scenario_id, None)

    bundle = run_ranking_pipeline(
        scenario_id,
        force_refresh=True,
        record_audit=False,
        context=ctx,
    )

    # Extract results
    ranked_vessels = [(v.vessel_id, v.posterior, v.priority.value) for v in bundle.vessels]
    top1_vid = bundle.vessels[0].vessel_id if bundle.vessels else None
    top3_vids = {v.vessel_id for v in bundle.vessels[:3]}

    # Top-1: any culprit is ranked #1
    top1_correct = top1_vid in culprits

    # Top-3: all culprits appear in top 3
    top3_correct = culprits.issubset(top3_vids)

    # IVFF: innocent vessels classified as HIGH
    innocent_high = 0
    innocent_count = 0
    for v in bundle.vessels:
        if v.vessel_id not in culprits:
            innocent_count += 1
            if v.priority.value == "HIGH":
                innocent_high += 1

    # Per-vessel labels and scores for calibration
    labels = []
    scores = []
    for v in bundle.vessels:
        is_culprit = 1 if v.vessel_id in culprits else 0
        labels.append(is_culprit)
        scores.append(v.posterior)

    return {
        "scenario_id": scenario_id,
        "scenario_class": scenario_class,
        "culprits": list(culprits),
        "top1_correct": top1_correct,
        "top3_correct": top3_correct,
        "innocent_high": innocent_high,
        "innocent_count": innocent_count,
        "ranked": ranked_vessels,
        "labels": labels,
        "scores": scores,
    }


def run_benchmark(
    scenarios_dir: Path,
    calib_count: int = 90,
    eval_count: int = 210,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Run full OccurisBench evaluation.

    1. Discover scenarios.
    2. Split into calib and eval sets.
    3. Run pipeline on all scenarios.
    4. Fit Platt calibration on calib split ONLY.
    5. Evaluate metrics on eval split.
    """
    t0 = time.time()

    # Ground truth isolation guard
    assert _ground_truth_isolation_check(), (
        "GUARD FAILED: src/ranking/ contains references to ground_truth.json or tools/bench. "
        "Production code must NEVER access ground truth."
    )

    # Discover scenarios
    manifest_path = scenarios_dir / "bench_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        scenario_ids = [s["scenario_id"] for s in manifest["scenarios"]]
    else:
        scenario_ids = sorted([
            d.name for d in scenarios_dir.iterdir()
            if d.is_dir() and d.name.startswith("scenario_")
        ])

    total = len(scenario_ids)
    print(f"[OccurisBench] Found {total} scenarios in {scenarios_dir}")

    if total < calib_count + eval_count:
        # Scale splits proportionally
        calib_count = int(total * 0.3)
        eval_count = total - calib_count
        print(f"[OccurisBench] Adjusted split: calib={calib_count}, eval={eval_count}")

    # Deterministic split using seed
    rng = np.random.RandomState(seed)
    indices = rng.permutation(total)
    calib_indices = set(indices[:calib_count])
    eval_indices = set(indices[calib_count:calib_count + eval_count])

    calib_results = []
    eval_results = []

    for i, sid in enumerate(scenario_ids):
        scenario_dir = scenarios_dir / sid
        if not scenario_dir.is_dir():
            continue

        result = run_single_scenario(scenario_dir)
        if "error" in result:
            print(f"  [SKIP] {sid}: {result['error']}")
            continue

        if i in calib_indices:
            result["split"] = "calib"
            calib_results.append(result)
        elif i in eval_indices:
            result["split"] = "eval"
            eval_results.append(result)

        status = "Y" if result["top1_correct"] else "N"
        if (i + 1) % 50 == 0 or i < 5:
            print(f"  [{i+1:3d}/{total}] {sid} ({result['scenario_class']}): Top1={status}")

    # --- Platt Calibration on CALIB split ONLY ---
    calib_labels = []
    calib_scores = []
    for r in calib_results:
        calib_labels.extend(r["labels"])
        calib_scores.extend(r["scores"])

    a_platt, b_platt = 1.0, 0.0
    if len(calib_labels) > 10:
        a_platt, b_platt = fit_platt_scaling(calib_labels, calib_scores)
        print(f"[OccurisBench] Platt parameters fitted on {len(calib_labels)} calib samples: A={a_platt:.4f}, B={b_platt:.4f}")

    # --- Evaluate on EVAL split ---
    eval_top1_correct = 0
    eval_top3_correct = 0
    eval_ivff_numer = 0
    eval_ivff_denom = 0
    eval_labels_all = []
    eval_scores_all = []
    class_breakdown = {}

    for r in eval_results:
        if r["top1_correct"]:
            eval_top1_correct += 1
        if r["top3_correct"]:
            eval_top3_correct += 1
        eval_ivff_numer += r["innocent_high"]
        eval_ivff_denom += r["innocent_count"]

        eval_labels_all.extend(r["labels"])
        eval_scores_all.extend(r["scores"])

        sc = r["scenario_class"]
        if sc not in class_breakdown:
            class_breakdown[sc] = {"total": 0, "top1": 0, "top3": 0}
        class_breakdown[sc]["total"] += 1
        if r["top1_correct"]:
            class_breakdown[sc]["top1"] += 1
        if r["top3_correct"]:
            class_breakdown[sc]["top3"] += 1

    n_eval = len(eval_results)
    top1_acc = eval_top1_correct / max(n_eval, 1)
    top3_cov = eval_top3_correct / max(n_eval, 1)
    ivff = eval_ivff_numer / max(eval_ivff_denom, 1)

    # Calibrate eval scores and compute ECE
    calibrated_scores = apply_platt_scaling(eval_scores_all, a_platt, b_platt)
    ece_val, ece_bins = compute_ece(eval_labels_all, calibrated_scores.tolist())

    runtime_s = time.time() - t0

    # Build report dict
    report = {
        "benchmark": "OccurisBench",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "code_revision": _code_revision(),
        "config_hash": _config_hash(),
        "seed": seed,
        "total_scenarios": total,
        "calib_count": len(calib_results),
        "eval_count": n_eval,
        "platt_params": {"A": round(a_platt, 6), "B": round(b_platt, 6)},
        "metrics": {
            "top1_accuracy": round(top1_acc, 4),
            "top3_coverage": round(top3_cov, 4),
            "ivff": round(ivff, 4),
            "ece": ece_val,
        },
        "targets": {
            "top1_accuracy": 0.80,
            "top3_coverage": 0.90,
            "ivff": 0.10,
            "ece": 0.10,
        },
        "pass_fail": {
            "top1_accuracy": "PASS" if top1_acc >= 0.80 else "FAIL",
            "top3_coverage": "PASS" if top3_cov >= 0.90 else "FAIL",
            "ivff": "PASS" if ivff <= 0.10 else "FAIL",
            "ece": "PASS" if ece_val <= 0.10 else "FAIL",
        },
        "class_breakdown": {
            sc: {
                "total": v["total"],
                "top1_accuracy": round(v["top1"] / max(v["total"], 1), 4),
                "top3_coverage": round(v["top3"] / max(v["total"], 1), 4),
            }
            for sc, v in class_breakdown.items()
        },
        "ece_reliability_bins": ece_bins,
        "runtime_seconds": round(runtime_s, 2),
        "ground_truth_isolation_passed": True,
        "disclaimer": "Investigation Priority ≠ Guilt. Physical consistency does not establish causation.",
    }

    # Print summary
    print(f"\n{'='*60}")
    print(f"  OccurisBench Results (eval split: {n_eval} scenarios)")
    print(f"{'='*60}")
    print(f"  Top-1 Accuracy: {top1_acc:.4f}  (target >= 0.80)  {'PASS' if top1_acc >= 0.80 else 'FAIL'}")
    print(f"  Top-3 Coverage: {top3_cov:.4f}  (target >= 0.90)  {'PASS' if top3_cov >= 0.90 else 'FAIL'}")
    print(f"  IVFF:           {ivff:.4f}  (target <= 0.10)  {'PASS' if ivff <= 0.10 else 'FAIL'}")
    print(f"  ECE:            {ece_val:.4f}  (target <= 0.10)  {'PASS' if ece_val <= 0.10 else 'FAIL'}")
    print(f"  Runtime:        {runtime_s:.1f}s")
    print(f"{'='*60}")
    print(f"  Per-class breakdown:")
    for sc, v in class_breakdown.items():
        t1 = round(v["top1"] / max(v["total"], 1), 2)
        t3 = round(v["top3"] / max(v["total"], 1), 2)
        print(f"    {sc:30s}  Top1={t1}  Top3={t3}  (n={v['total']})")
    print(f"{'='*60}\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="OccurisBench Runner")
    parser.add_argument("--scenarios", type=str, default="data/bench/scenarios",
                        help="Directory containing generated scenarios")
    parser.add_argument("--split", type=str, default="calib:90,eval:210",
                        help="Split specification (calib:N,eval:M)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split")
    parser.add_argument("--out", type=str, default="data/bench/bench_results.json",
                        help="Output results JSON path")
    args = parser.parse_args()

    # Parse split spec
    parts = args.split.split(",")
    calib_count = 90
    eval_count = 210
    for part in parts:
        key, val = part.strip().split(":")
        if key.strip() == "calib":
            calib_count = int(val.strip())
        elif key.strip() == "eval":
            eval_count = int(val.strip())

    report = run_benchmark(
        scenarios_dir=Path(args.scenarios),
        calib_count=calib_count,
        eval_count=eval_count,
        seed=args.seed,
    )

    # Save results
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OccurisBench] Results saved to {out_path}")


if __name__ == "__main__":
    main()
