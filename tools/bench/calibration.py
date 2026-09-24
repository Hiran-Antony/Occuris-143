"""
OccurisBench — Platt Scaling & Calibration (§10)

Provides:
- fit_platt_scaling: Fit 1D logistic calibration parameters (A, B) on calibration split.
- apply_platt_scaling: Transform uncalibrated posteriors into calibrated probabilities.
- compute_ece: Compute Expected Calibration Error across reliability bins.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple
import numpy as np
from scipy.optimize import minimize


def fit_platt_scaling(
    y_true: List[int] | np.ndarray,
    uncalibrated_scores: List[float] | np.ndarray,
) -> Tuple[float, float]:
    """
    Fit Platt scaling parameters (A, B) using regularized logistic regression:
    P(y=1 | s) = 1 / (1 + exp(-(A * s + B)))
    
    Uses Platt (1999) target smoothing:
    t+ = (N+ + 1) / (N+ + 2)
    t- = 1 / (N- + 2)
    """
    y = np.asarray(y_true, dtype=float)
    s = np.asarray(uncalibrated_scores, dtype=float)
    
    n_pos = np.sum(y == 1.0)
    n_neg = np.sum(y == 0.0)
    
    # Target smoothing per Platt (1999)
    t_pos = (n_pos + 1.0) / (n_pos + 2.0)
    t_neg = 1.0 / (n_neg + 2.0)
    targets = np.where(y == 1.0, t_pos, t_neg)
    
    def loss(params: np.ndarray) -> float:
        a, b = params
        logits = a * s + b
        # Stable log-loss
        p = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
        eps = 1e-12
        p_clipped = np.clip(p, eps, 1.0 - eps)
        bce = -np.mean(targets * np.log(p_clipped) + (1.0 - targets) * np.log(1.0 - p_clipped))
        # L2 penalty
        l2 = 1e-4 * (a ** 2 + b ** 2)
        return float(bce + l2)

    init_params = np.array([1.0, 0.0])
    res = minimize(loss, init_params, method="L-BFGS-B")
    a_opt, b_opt = float(res.x[0]), float(res.x[1])
    return a_opt, b_opt


def apply_platt_scaling(
    uncalibrated_scores: List[float] | np.ndarray,
    a: float,
    b: float,
) -> np.ndarray:
    """Apply fitted parameters (A, B) to convert scores to calibrated probabilities."""
    s = np.asarray(uncalibrated_scores, dtype=float)
    logits = a * s + b
    probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
    return np.clip(probs, 0.0, 1.0)


def compute_ece(
    y_true: List[int] | np.ndarray,
    y_probs: List[float] | np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Compute Expected Calibration Error (ECE) and reliability bin table.
    
    ECE = sum_{m=1}^M (|B_m| / N) * |acc(B_m) - conf(B_m)|
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_probs, dtype=float)
    n = len(y)
    if n == 0:
        return 0.0, []

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins_data: List[Dict[str, Any]] = []
    total_ece = 0.0

    for i in range(n_bins):
        low, high = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (p >= low) & (p <= high)
        else:
            mask = (p >= low) & (p < high)

        count = int(np.sum(mask))
        if count > 0:
            bin_acc = float(np.mean(y[mask]))
            bin_conf = float(np.mean(p[mask]))
            err = abs(bin_acc - bin_conf)
            weighted_err = (count / n) * err
            total_ece += weighted_err
        else:
            bin_acc = 0.0
            bin_conf = (low + high) / 2.0
            err = 0.0
            weighted_err = 0.0

        bins_data.append({
            "bin_index": i,
            "range": [round(float(low), 2), round(float(high), 2)],
            "count": count,
            "accuracy": round(bin_acc, 4),
            "confidence": round(bin_conf, 4),
            "abs_error": round(err, 4),
        })

    return round(float(total_ece), 4), bins_data
