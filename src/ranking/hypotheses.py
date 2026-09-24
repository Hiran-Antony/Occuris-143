"""
Occuris Module 8 — Multi-Source Hypothesis Testing

Evaluates competing hypotheses for slick origins:
  H1: Single-source vessel discharge
  H2: Coordinated two-source discharge (ship-to-ship transfer or synchronized)
  H3: Two independent source discharges
  H4: Spill plus natural/biogenic look-alike
  H5: Natural seep plus vessel discharge

Applies Bayesian Information Criterion (BIC) penalties and softmax over testable hypotheses.
Untestable hypotheses return INSUFFICIENT_DATA status.

HONESTY DOCTRINE: Investigation Priority != Guilt.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ais.schemas import HypothesisPosterior
from src.ranking.evidence_engine import load_ranking_config
from src.ranking.schemas import HypothesisReport, HypothesisTestItem


def test_hypotheses(
    case_id: str,
    spillsplit_data: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> HypothesisReport:
    """
    Test competing hypotheses H1-H5 for a case.

    Reuses SpillSplit's one-source and two-source metrics if available.
    H1: Single-source forward simulation IoU and BIC.
    H2: Two-source forward simulation IoU and BIC.
    H3-H5: Schema-ready; return INSUFFICIENT_DATA with explicit reasons.
    """
    cfg = config or load_ranking_config()
    hyp_cfg = cfg.get("hypotheses", {})

    # Load spillsplit data if not passed
    if spillsplit_data is None:
        spillsplit_path = Path("data/processed") / f"{case_id}_spillsplit.json"
        if spillsplit_path.exists():
            try:
                with open(spillsplit_path, "r", encoding="utf-8") as f:
                    spillsplit_data = json.load(f)
            except Exception:
                spillsplit_data = None

    hypotheses: List[HypothesisTestItem] = []

    if spillsplit_data is None:
        # No spillsplit output available
        for h_id in ["H1", "H2", "H3", "H4", "H5"]:
            desc = hyp_cfg.get(f"{h_id}_single_source" if h_id == "H1" else f"{h_id}_...", {}).get("description", f"Hypothesis {h_id}")
            hypotheses.append(
                HypothesisTestItem(
                    id=h_id,
                    description=desc,
                    posterior=0.0,
                    log_likelihood=0.0,
                    penalty=0.0,
                    status="INSUFFICIENT_DATA",
                )
            )
        return HypothesisReport(
            case_id=case_id,
            hypotheses=hypotheses,
            preferred_hypothesis_id="INSUFFICIENT_DATA",
            explanation="SpillSplit data unavailable for multi-source hypothesis testing.",
        )

    # Extract H1 and H2 metrics
    one_src = spillsplit_data.get("one_source", {})
    two_src = spillsplit_data.get("two_source", {})

    bic_1 = float(one_src.get("bic", 100.0))
    iou_1 = float(one_src.get("iou", 0.10))
    bic_2 = float(two_src.get("bic", 110.0))
    iou_2 = float(two_src.get("iou", 0.10))

    w_bic_1 = float(hyp_cfg.get("H1_single_source", {}).get("bic_penalty_weight", 1.0))
    w_bic_2 = float(hyp_cfg.get("H2_coordinated_two_source", {}).get("bic_penalty_weight", 2.0))

    # Log likelihood approximations from IoU (or BIC inverted)
    # BIC = -2 * ln(L) + k * ln(n). Here we evaluate score = log_lik - penalty
    # Penalized likelihood score = -0.5 * BIC * weight
    score_1 = -0.5 * bic_1 * w_bic_1
    score_2 = -0.5 * bic_2 * w_bic_2

    # In addition, incorporate IoU into the evidence score
    log_lik_1 = math.log(max(iou_1, 1e-4)) * 10.0
    log_lik_2 = math.log(max(iou_2, 1e-4)) * 10.0

    total_score_1 = log_lik_1 - (bic_1 * 0.05 * w_bic_1)
    total_score_2 = log_lik_2 - (bic_2 * 0.05 * w_bic_2)

    # Softmax over {H1, H2}
    max_score = max(total_score_1, total_score_2)
    exp_1 = math.exp(total_score_1 - max_score)
    exp_2 = math.exp(total_score_2 - max_score)
    denom = exp_1 + exp_2

    post_1 = exp_1 / denom
    post_2 = exp_2 / denom

    h1_item = HypothesisTestItem(
        id="H1",
        description=hyp_cfg.get("H1_single_source", {}).get(
            "description", "Single vessel responsible for observed slick"
        ),
        posterior=round(post_1, 4),
        log_likelihood=round(log_lik_1, 4),
        penalty=round(bic_1 * 0.05 * w_bic_1, 4),
        status="TESTABLE",
        bic_score=bic_1,
    )

    h2_item = HypothesisTestItem(
        id="H2",
        description=hyp_cfg.get("H2_coordinated_two_source", {}).get(
            "description", "Two vessels coordinated discharge (ship-to-ship transfer or synchronized)"
        ),
        posterior=round(post_2, 4),
        log_likelihood=round(log_lik_2, 4),
        penalty=round(bic_2 * 0.05 * w_bic_2, 4),
        status="TESTABLE",
        bic_score=bic_2,
    )

    # H3-H5 return INSUFFICIENT_DATA
    h3_item = HypothesisTestItem(
        id="H3",
        description=hyp_cfg.get("H3_two_independent", {}).get(
            "description", "Two independent vessels discharged separately"
        ),
        posterior=0.0,
        log_likelihood=0.0,
        penalty=0.0,
        status="INSUFFICIENT_DATA",
    )

    h4_item = HypothesisTestItem(
        id="H4",
        description=hyp_cfg.get("H4_spill_plus_lookalike", {}).get(
            "description", "One vessel discharge + one natural/biogenic slick"
        ),
        posterior=0.0,
        log_likelihood=0.0,
        penalty=0.0,
        status="INSUFFICIENT_DATA",
    )

    h5_item = HypothesisTestItem(
        id="H5",
        description=hyp_cfg.get("H5_seep_plus_spill", {}).get(
            "description", "Natural seep + vessel discharge"
        ),
        posterior=0.0,
        log_likelihood=0.0,
        penalty=0.0,
        status="INSUFFICIENT_DATA",
    )

    hypotheses = [h1_item, h2_item, h3_item, h4_item, h5_item]

    preferred_id = "H1" if post_1 >= post_2 else "H2"
    if preferred_id == "H1":
        explanation = (
            f"H1 (Single-source) preferred with posterior {post_1:.3f} vs H2 {post_2:.3f}. "
            f"BIC={bic_1:.1f} vs {bic_2:.1f}; IoU={iou_1:.3f} vs {iou_2:.3f}."
        )
    else:
        explanation = (
            f"H2 (Two-source coordinated) preferred with posterior {post_2:.3f} vs H1 {post_1:.3f}. "
            f"BIC={bic_2:.1f} vs {bic_1:.1f}; IoU={iou_2:.3f} vs {iou_1:.3f}."
        )

    return HypothesisReport(
        case_id=case_id,
        hypotheses=hypotheses,
        preferred_hypothesis_id=preferred_id,
        explanation=explanation,
    )


def to_hypothesis_posteriors(report: HypothesisReport) -> List[HypothesisPosterior]:
    """Convert HypothesisReport to schema-compatible HypothesisPosterior list."""
    posteriors = []
    for h in report.hypotheses:
        posteriors.append(
            HypothesisPosterior(
                hypothesis_id=h.id,
                description=h.description,
                posterior=h.posterior,
                bic_penalty=h.penalty,
                status=h.status,
            )
        )
    return posteriors
