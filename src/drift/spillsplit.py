"""
Module 4 — SpillSplit
Determines whether the observed oil slick is better explained by one probable
release zone (H1) or two spatially and physically distinct release zones (H2).

Pipeline:
    Origin Particle Cloud (Module 3)
        ↓
    GMM Candidate Source Separation  (H1 = 1-component, H2 = 2-component)
        ↓
    Source Separation Validity Check  (Haversine distance > MIN_SEP_KM)
        ↓
    Stability Testing (bootstrap sub-sampling across seeds)
        ↓
    Forward Physical Reconstruction   (H1 and H2 via RK45 advection)
        ↓
    Physical Fit Metrics              (IoU, centroid dist, area diff, shape)
        ↓
    BIC Complexity Penalty
        ↓
    Weighted Decision                 (One Source / Two Sources / Inconclusive)
        ↓
    JSON + Diagnostic Plot saved
"""
import sys, json, argparse
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import CASES, DATA_PROCESSED, PIXEL_SCALE_M
from drift.velocity_field import VelocityField
from drift.rk4 import RK45DriftEngine

# ── Algorithm constants ────────────────────────────────────────────────────────
# Configurable MVP thresholds — document that these must be calibrated against
# controlled one-source and two-source test cases before operational use.
MIN_SEP_KM        = 5.0    # Minimum km between GMM-2 centres for distinct sources.
                            # MVP prototype value; should be compared to reconstruction
                            # uncertainty from Module 3 particle spread.
STABILITY_FRACS   = [0.80, 0.90, 1.00]  # bootstrap sub-sample fractions
STABILITY_SEEDS   = [10, 42, 99, 137, 200]  # random seeds per fraction (15 runs total)
STABILITY_SEP_FACTOR = 0.5  # max acceptable centroid variation as fraction of separation.
                              # e.g. 0.5 means variation must be < 50% of source separation.
                              # This makes stability relative to evidence, not an absolute km.
BIC_DELTA_THRESH  = 6.0   # BIC_H1 - BIC_H2 must exceed this (lower BIC is better;
                            # so positive delta means H2 is statistically justified).
IOU_DELTA_THRESH  = 0.04  # Minimum IoU improvement for H2 over H1 physical reconstruction.
                            # Prototype threshold; should be validated against test cases.
FORWARD_N_PX      = 30    # particles released per GMM component for forward sim
FORWARD_HOURS     = 24.0  # forward hours — matches hindcast window from Module 3
MASK_SIZE         = 256   # must match MODEL_IMG_SIZE from Module 1 training

EARTH_R_M = 6_371_000.0


# ── Haversine ─────────────────────────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km."""
    r = EARTH_R_M / 1000.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
    return 2 * r * np.arcsin(np.sqrt(a))


# ── Load Module 3 particles ───────────────────────────────────────────────────
def load_origin_particles(case_id: str) -> tuple:
    """Load backward-drift origin particle cloud from Module 3 JSON."""
    p = DATA_PROCESSED / f"{case_id}_drift.json"
    if not p.exists():
        raise FileNotFoundError(
            f"Module 3 output missing: {p}\n"
            f"Run Module 3 backward_drift.py first."
        )
    d = json.loads(p.read_text())
    lats = np.array(d["origin_lats"], dtype=np.float64)
    lons = np.array(d["origin_lons"], dtype=np.float64)
    return lats, lons


# ── Load observed predicted mask (Module 1) ───────────────────────────────────
def load_pred_mask(case_id: str) -> np.ndarray:
    """Load the SegFormer predicted binary mask from Module 1."""
    p = DATA_PROCESSED / f"{case_id}_pred_mask.npy"
    if not p.exists():
        raise FileNotFoundError(f"Module 1 mask missing: {p}")
    mask = np.load(p)
    return (mask > 0).astype(np.uint8)


# ── GMM fitting ───────────────────────────────────────────────────────────────
def fit_gmm(lats: np.ndarray, lons: np.ndarray, n: int, seed: int = 42) -> dict:
    """
    Fit a Gaussian Mixture Model with n components.
    Returns BIC, component means, and covariance matrices (used for seeding
    forward simulations from the full Gaussian distribution, not just centroid).
    Note: Lower BIC is better. BIC_H1 - BIC_H2 > threshold means H2 is justified.
    """
    X = np.column_stack([lats, lons])
    gmm = GaussianMixture(n_components=n, covariance_type="full",
                          random_state=seed, n_init=5, max_iter=300)
    gmm.fit(X)
    bic = gmm.bic(X)
    components = []
    for i in range(n):
        w    = float(gmm.weights_[i])
        lat  = float(gmm.means_[i, 0])
        lon  = float(gmm.means_[i, 1])
        cov  = gmm.covariances_[i].tolist()   # 2x2 covariance matrix [lat,lon]
        components.append({
            "id":        chr(65 + i),
            "weight":    round(w, 4),
            "latitude":  round(lat, 5),
            "longitude": round(lon, 5),
            "covariance": cov,            # preserved for covariance-based seeding
        })
    components.sort(key=lambda x: x["weight"], reverse=True)
    return {"bic": round(bic, 3), "components": components}


# ── Stability test ────────────────────────────────────────────────────────────
def stability_test(lats: np.ndarray, lons: np.ndarray, sep_km: float) -> dict:
    """
    Bootstrap GMM(n=2) across sub-sample fractions and random seeds.

    KEY IMPROVEMENT over simple absolute threshold:
    Stability is measured relative to the source separation, not against a fixed km.
    Criterion: max centroid variation < STABILITY_SEP_FACTOR * sep_km

    Rationale: If two sources are only 6 km apart, variation of 5 km is not 'stable'.
    If two sources are 50 km apart, variation of 5 km is highly stable.
    This makes the test scale with the actual evidence being evaluated.
    """
    n = len(lats)
    centroid_As, centroid_Bs = [], []

    for frac in STABILITY_FRACS:
        for seed in STABILITY_SEEDS:
            rng = np.random.default_rng(seed)
            k = max(4, int(n * frac))
            idx = rng.choice(n, k, replace=False)
            sub_lats, sub_lons = lats[idx], lons[idx]
            try:
                res = fit_gmm(sub_lats, sub_lons, n=2, seed=seed)
                comps = res["components"]
                centroid_As.append((comps[0]["latitude"], comps[0]["longitude"]))
                centroid_Bs.append((comps[1]["latitude"], comps[1]["longitude"]))
            except Exception:
                pass  # GMM may not converge on very small subsets — silently skip

    if len(centroid_As) < 3:
        return {
            "stable": False, "score": 0.0,
            "variation_km": 999.0, "sep_km": round(sep_km, 3),
            "stability_sep_factor": STABILITY_SEP_FACTOR,
            "n_bootstrap_runs": 0,
            "note": "Too few successful GMM fits for stability test",
        }

    # Compute max centroid displacement across bootstrap runs
    def spread_km(pts):
        """95th percentile displacement from mean centroid position (km)."""
        lts = np.array([p[0] for p in pts])
        lns = np.array([p[1] for p in pts])
        mean_lat, mean_lon = lts.mean(), lns.mean()
        dists = np.array([
            haversine_km(mean_lat, mean_lon, lt, ln)
            for lt, ln in zip(lts, lns)
        ])
        return float(np.percentile(dists, 95))  # 95th pctile, not just mean

    var_A = spread_km(centroid_As)
    var_B = spread_km(centroid_Bs)
    max_var = max(var_A, var_B)

    # Adaptive threshold: variation must be small relative to separation
    adaptive_thresh = STABILITY_SEP_FACTOR * sep_km
    stable = bool(sep_km > 0 and max_var < adaptive_thresh)

    # Normalised score: 1 = perfectly stable, 0 = variation equals separation
    if sep_km > 0:
        score = round(float(np.clip(1.0 - max_var / (sep_km + 1e-9), 0, 1)), 4)
    else:
        score = 0.0

    note = (
        f"Stable (var={max_var:.2f}km < {adaptive_thresh:.2f}km threshold)"
        if stable
        else f"Unstable (var={max_var:.2f}km >= {adaptive_thresh:.2f}km threshold)"
    )

    return {
        "stable": stable,
        "score": score,
        "variation_km": round(max_var, 3),
        "adaptive_threshold_km": round(adaptive_thresh, 3),
        "sep_km": round(sep_km, 3),
        "stability_sep_factor": STABILITY_SEP_FACTOR,
        "n_bootstrap_runs": len(centroid_As),
        "note": note,
    }


# ── Forward simulation ────────────────────────────────────────────────────────
def forward_simulate_from_gmm(comp: dict, n_px: int, vf: VelocityField,
                               seed: int = 42) -> tuple:
    """
    Release n_px particles sampled from the GMM component's Gaussian distribution
    (mean + covariance), then advect forward.

    KEY IMPROVEMENT: Instead of releasing all particles from a single centroid point,
    we sample from the full GMM covariance ellipse. This propagates the reconstruction
    uncertainty from Module 3 through the forward simulation, making the simulated
    spill footprint physically more realistic.
    """
    mean = np.array([comp["latitude"], comp["longitude"]])
    cov  = np.array(comp["covariance"])    # 2x2 matrix [lat, lon]

    rng = np.random.default_rng(seed)
    # Sample release positions from the GMM component distribution
    samples = rng.multivariate_normal(mean, cov, size=n_px)
    seed_lats = samples[:, 0]
    seed_lons = samples[:, 1]

    engine = RK45DriftEngine(
        velocity_func=vf.get_velocity,
        diffusivity_func=vf.get_eddy_diffusivity
    )
    f_lats, f_lons, _ = engine.integrate(
        seed_lats=seed_lats, seed_lons=seed_lons,
        duration_hours=FORWARD_HOURS, dt_minutes=10.0, backward=False
    )
    return f_lats, f_lons


def particles_to_mask(lats: np.ndarray, lons: np.ndarray,
                      case_id: str, size: int = MASK_SIZE) -> np.ndarray:
    """
    Rasterise particle cloud onto a size×size binary mask using the
    case bounding box from config.
    """
    bbox = CASES[case_id]["spill_bbox"]
    lat_min, lat_max = bbox["lat_min"], bbox["lat_max"]
    lon_min, lon_max = bbox["lon_min"], bbox["lon_max"]

    # Clip to bbox
    valid = ((lats >= lat_min) & (lats <= lat_max) &
             (lons >= lon_min) & (lons <= lon_max))
    if valid.sum() == 0:
        return np.zeros((size, size), dtype=np.uint8)

    rows = ((lat_max - lats[valid]) / (lat_max - lat_min) * (size - 1)).astype(int)
    cols = ((lons[valid] - lon_min) / (lon_max - lon_min) * (size - 1)).astype(int)
    rows = np.clip(rows, 0, size - 1)
    cols = np.clip(cols, 0, size - 1)

    mask = np.zeros((size, size), dtype=np.uint8)
    mask[rows, cols] = 1

    # Dilate to create a reasonable spill blob from sparse particles
    kernel = np.ones((9, 9), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=2)
    return mask


# ── Physical fit metrics ──────────────────────────────────────────────────────
def compute_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Intersection over Union between two binary masks."""
    intersection = np.logical_and(mask_a, mask_b).sum()
    union        = np.logical_or(mask_a, mask_b).sum()
    return float(intersection / (union + 1e-6))


def compute_centroid_distance_km(mask_a: np.ndarray, mask_b: np.ndarray,
                                  case_id: str) -> float:
    """Euclidean centroid distance in km between two masks."""
    def centroid_geo(mask):
        rows, cols = np.where(mask > 0)
        if len(rows) == 0:
            return None, None
        bbox = CASES[case_id]["spill_bbox"]
        H, W  = mask.shape
        lat = bbox["lat_max"] - (rows.mean() / H) * (bbox["lat_max"] - bbox["lat_min"])
        lon = bbox["lon_min"] + (cols.mean() / W) * (bbox["lon_max"] - bbox["lon_min"])
        return float(lat), float(lon)

    lat_a, lon_a = centroid_geo(mask_a)
    lat_b, lon_b = centroid_geo(mask_b)
    if lat_a is None or lat_b is None:
        return 999.0
    return haversine_km(lat_a, lon_a, lat_b, lon_b)


def compute_area_diff_pct(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Area difference as percent of observed mask area."""
    area_obs = mask_a.sum()
    area_sim = mask_b.sum()
    if area_obs == 0:
        return 100.0
    return round(abs(area_obs - area_sim) / area_obs * 100.0, 2)


def compute_physical_fit(obs_mask, sim_mask, case_id) -> dict:
    return {
        "iou":          round(compute_iou(obs_mask, sim_mask), 4),
        "centroid_dist_km": round(compute_centroid_distance_km(obs_mask, sim_mask, case_id), 3),
        "area_diff_pct":    compute_area_diff_pct(obs_mask, sim_mask),
    }


# ── Decision logic ────────────────────────────────────────────────────────────
def decide(h1: dict, h2: dict, sep_km: float, stability: dict) -> dict:
    """
    GATED SEQUENTIAL DECISION — not a simple vote count.

    Gate 1 — Separation valid?
        NO  → One Source Zone (H2 has no meaningfully distinct clusters)
        YES → Gate 2

    Gate 2 — Stability valid?
        NO  → One Source Zone (H2 clusters are not reproducible)
        YES → Gate 3

    Gate 3 — Physics improves?
        NO  → One Source Zone (H2 doesn't explain the observed spill better)
        YES → Gate 4

    Gate 4 — BIC justifies complexity?
        YES → Two Source Zones (Supported)
        NO  → Inconclusive (physics supports H2 but statistical penalty is too high)

    This gated approach ensures that physical reconstruction (Gate 3) is the
    primary evidence, and BIC (Gate 4) is a complexity check on top — not a
    factor that can override poor physical fit.

    Inconclusive is a genuine third state; it is NOT silently converted to
    One Source. Downstream modules should carry confidence_status = INCONCLUSIVE
    and may use H1 as a fallback while explicitly flagging the ambiguity.
    """
    bic_improvement = h1["bic"] - h2["bic"]        # positive = H2 has lower BIC (better fit)
    iou_improvement = h2["physical"]["iou"] - h1["physical"]["iou"]
    separation_ok   = sep_km >= MIN_SEP_KM
    stable          = stability["stable"]
    physics_ok      = iou_improvement >= IOU_DELTA_THRESH
    bic_ok          = bic_improvement >= BIC_DELTA_THRESH

    # ── Gated evaluation ─────────────────────────────────────────────────────
    gate_log = []

    # Gate 1: Separation
    if not separation_ok:
        verdict           = "One Source Zone"
        confidence        = "H2 Not Tested — separation below minimum"
        confidence_status = "ONE_SOURCE_SEP_FAIL"
        reason            = (
            f"GMM-2 cluster centres are {sep_km:.2f} km apart, below the {MIN_SEP_KM} km "
            f"minimum required for distinct source zones. The backward-drift origin cloud "
            f"does not support two spatially distinguishable release zones."
        )
        gate_log.append(f"GATE1 FAIL: sep={sep_km:.2f}km < {MIN_SEP_KM}km minimum")

    # Gate 2: Stability
    elif not stable:
        verdict           = "One Source Zone"
        confidence        = "H2 Not Supported — clusters unstable across bootstrap samples"
        confidence_status = "ONE_SOURCE_STABILITY_FAIL"
        reason            = (
            f"GMM-2 cluster positions shift {stability['variation_km']} km across bootstrap "
            f"sub-samples, exceeding the adaptive threshold of {stability['adaptive_threshold_km']} km "
            f"({STABILITY_SEP_FACTOR}x source separation). The two-cluster solution is not "
            f"reproducible — the spatial structure of the origin cloud cannot reliably place "
            f"two distinct source zones."
        )
        gate_log.append(f"GATE2 FAIL: stability score={stability['score']:.3f} — clusters unstable")

    # Gate 3: Physical fit
    elif not physics_ok:
        verdict           = "One Source Zone"
        confidence        = "H2 Not Supported — two-source reconstruction performed worse"
        confidence_status = "ONE_SOURCE_PHYSICS_FAIL"
        reason            = (
            f"Forward physical reconstruction with two sources (H2 IoU={h2['physical']['iou']:.4f}) "
            f"does not materially improve on the one-source reconstruction "
            f"(H1 IoU={h1['physical']['iou']:.4f}, delta={iou_improvement:.4f} < threshold {IOU_DELTA_THRESH}). "
            f"The observed spill is better explained by a single release zone."
        )
        gate_log.append(
            f"GATE3 FAIL: IoU improvement={iou_improvement:.4f} < {IOU_DELTA_THRESH} threshold\n"
            f"            H2 does not materially improve physical reconstruction"
        )

    # Gate 4: BIC complexity penalty
    elif bic_ok:
        verdict           = "Two Source Zones"
        confidence        = "Supported — all four gates passed"
        confidence_status = "TWO_SOURCE_SUPPORTED"
        reason            = (
            f"All gates passed: separation={sep_km:.2f} km, stable (variation={stability['variation_km']} km), "
            f"H2 improves physical fit (IoU delta={iou_improvement:.4f}), "
            f"BIC improvement={bic_improvement:.3f} justifies the extra source."
        )
        gate_log.append(
            f"ALL GATES PASS: sep={sep_km:.2f}km, stable, IoU+{iou_improvement:.4f}, "
            f"BIC improvement={bic_improvement:.3f}"
        )
    else:
        # Physics supports H2 but BIC penalty is too high — genuine ambiguity
        verdict           = "Inconclusive"
        confidence        = "Physics supports H2 but statistical penalty insufficient"
        confidence_status = "INCONCLUSIVE"
        reason            = (
            f"Physical reconstruction favours H2 (IoU +{iou_improvement:.4f}) but "
            f"BIC improvement ({bic_improvement:.3f}) does not exceed the {BIC_DELTA_THRESH} threshold. "
            f"Use H1 as operational fallback; flag confidence_status=INCONCLUSIVE in "
            f"downstream modules (Module 5 AIS, Module 6 reporting)."
        )
        gate_log.append(f"GATE4 AMBIGUOUS: physics OK but BIC={bic_improvement:.3f} < {BIC_DELTA_THRESH}")

    return {
        "verdict":            verdict,
        "confidence":         confidence,
        "confidence_status":  confidence_status,   # machine-readable enum
        "reason":             reason,               # human-readable explanation
        "gate_log":           gate_log,
        "factors": {
            "separation_km":       round(sep_km, 3),
            "separation_ok":       bool(separation_ok),
            "stability_stable":    bool(stable),
            "stability_score":     stability["score"],
            "stability_variation_km": stability["variation_km"],
            "iou_h1":              round(h1["physical"]["iou"], 4),
            "iou_h2":              round(h2["physical"]["iou"], 4),
            "iou_improvement":     round(iou_improvement, 4),
            "iou_favours_two":     bool(physics_ok),
            "bic_improvement":     round(bic_improvement, 3),
            "bic_favours_two":     bool(bic_ok),
            "iou_threshold_note":  "Prototype MVP threshold (0.04); calibrate against known test cases.",
            "sep_threshold_note":  "Prototype MVP threshold (5 km); relate to Module 3 reconstruction uncertainty.",
        }
    }



# ── Diagnostic plot ───────────────────────────────────────────────────────────
def save_diagnostic(case_id, obs_mask, h1_mask, h2_mask,
                     origin_lats, origin_lons,
                     h1_comps, h2_comps, verdict, out_dir):
    fig, axes = plt.subplots(1, 5, figsize=(28, 5.5))
    fig.patch.set_facecolor("#0d1117")
    for ax in axes:
        ax.set_facecolor("#0d1225")
        ax.axis("off")

    # Panel 0 — origin particles + GMM-1 centroid
    axes[0].scatter(origin_lons, origin_lats, c="#00e676", s=12, alpha=0.7, zorder=5)
    c1 = h1_comps[0]
    axes[0].plot(c1["longitude"], c1["latitude"], "y*", markersize=18, zorder=8)
    axes[0].set_title("H1 Origin Cloud\n(GMM-1 centroid)", color="white", fontsize=9)

    # Panel 1 — GMM-2 clusters
    colors = ["#ff6b35", "#4a9eff"]
    for i, comp in enumerate(h2_comps):
        mask_pts = ((origin_lats > comp["latitude"] - 0.5) &
                    (origin_lats < comp["latitude"] + 0.5))
        axes[1].scatter(origin_lons[mask_pts], origin_lats[mask_pts],
                        c=colors[i % 2], s=14, alpha=0.6, zorder=5)
        axes[1].plot(comp["longitude"], comp["latitude"], "*", color=colors[i % 2],
                     markersize=16, zorder=8, label=f"Source {comp['id']}")
    axes[1].legend(facecolor="#1a1a2e", labelcolor="white", fontsize=7)
    axes[1].set_title("H2 Origin Cloud\n(GMM-2 centroids)", color="white", fontsize=9)

    # Panel 2 — observed mask
    axes[2].imshow(obs_mask, cmap="magma", vmin=0, vmax=1)
    axes[2].set_title("Observed SAR Mask\n(SegFormer M1)", color="white", fontsize=9)

    # Panel 3 — H1 forward simulation mask
    axes[3].imshow(h1_mask, cmap="Blues", vmin=0, vmax=1)
    axes[3].set_title("H1 Simulated Mask\n(1-Source forward)", color="white", fontsize=9)

    # Panel 4 — H2 forward simulation mask
    axes[4].imshow(h2_mask, cmap="Oranges", vmin=0, vmax=1)
    verdict_short = "2-Source" if "Two" in verdict else "1-Source"
    axes[4].set_title(f"H2 Simulated Mask\n({verdict_short} forward)", color="white", fontsize=9)

    title = f"Occuris — SpillSplit — {case_id}  |  Verdict: {verdict}"
    fig.suptitle(title, color="white", fontsize=11, y=1.01)

    plt.tight_layout()
    out_path = out_dir / f"{case_id}_spillsplit.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return out_path


# ── Case processor ────────────────────────────────────────────────────────────
def process_case(case_id: str) -> dict:
    print(f"\n  [{case_id.upper()}]")

    # 1. Load inputs
    origin_lats, origin_lons = load_origin_particles(case_id)
    obs_mask = load_pred_mask(case_id)
    print(f"    Particles loaded : {len(origin_lats)}")

    # 2. Fit GMMs
    h1_gmm = fit_gmm(origin_lats, origin_lons, n=1)
    h2_gmm = fit_gmm(origin_lats, origin_lons, n=2)
    print(f"    BIC H1           : {h1_gmm['bic']}")
    print(f"    BIC H2           : {h2_gmm['bic']}")

    # 3. Source separation check
    comps = h2_gmm["components"]
    sep_km = haversine_km(comps[0]["latitude"], comps[0]["longitude"],
                           comps[1]["latitude"], comps[1]["longitude"]) if len(comps) == 2 else 0.0
    print(f"    Source sep       : {round(sep_km, 2)} km (min={MIN_SEP_KM} km)")

    # 4. Stability test (adaptive: threshold is relative to separation, not absolute km)
    stability = stability_test(origin_lats, origin_lons, sep_km)
    print(f"    Stability score  : {stability['score']}  ({stability['note']})")
    print(f"    Stability thresh : {stability['adaptive_threshold_km']} km (={STABILITY_SEP_FACTOR}x sep)")

    # 5. Forward simulation + physical fit
    # Seeds are sampled from the full GMM covariance distribution, not just the centroid.
    # This preserves reconstruction uncertainty through the forward simulation.
    vf = VelocityField()

    # H1 forward (from GMM-1 covariance)
    h1_comp = h1_gmm["components"][0]
    h1_lats, h1_lons = forward_simulate_from_gmm(h1_comp, FORWARD_N_PX, vf, seed=42)
    h1_sim_mask = particles_to_mask(h1_lats, h1_lons, case_id)
    h1_physical  = compute_physical_fit(obs_mask, h1_sim_mask, case_id)
    print(f"    H1 IoU           : {h1_physical['iou']}")

    # H2 forward (from each GMM-2 component's covariance; combined mask)
    h2_all_lats, h2_all_lons = np.array([]), np.array([])
    for i, comp in enumerate(comps):
        fl, flo = forward_simulate_from_gmm(comp, FORWARD_N_PX // 2 + 1, vf, seed=42 + i)
        h2_all_lats = np.concatenate([h2_all_lats, fl])
        h2_all_lons = np.concatenate([h2_all_lons, flo])
    h2_sim_mask = particles_to_mask(h2_all_lats, h2_all_lons, case_id)
    h2_physical  = compute_physical_fit(obs_mask, h2_sim_mask, case_id)
    print(f"    H2 IoU           : {h2_physical['iou']}")

    # 6. Decision
    h1_full = {**h1_gmm, "physical": h1_physical}
    h2_full = {**h2_gmm, "physical": h2_physical}
    decision = decide(h1_full, h2_full, sep_km, stability)

    print(f"    Verdict          : {decision['verdict']}")
    print(f"    Confidence       : {decision['confidence']}")

    # 7. Build output JSON
    source_zones = []
    if "Two" in decision["verdict"]:
        for comp in comps:
            source_zones.append({
                "id": comp["id"],
                "latitude": comp["latitude"],
                "longitude": comp["longitude"],
                "weight": comp["weight"],
            })
    else:
        source_zones.append({
            "id": "A",
            "latitude": h1_comp["latitude"],
            "longitude": h1_comp["longitude"],
            "weight": 1.0,
        })

    result = {
        "case_id": case_id,
        "result":  decision["verdict"],
        "confidence": decision["confidence"],
        "source_zones": source_zones,
        "source_separation_km": round(sep_km, 3),
        "stability": stability,
        "one_source": {
            "bic": h1_gmm["bic"],
            "iou": h1_physical["iou"],
            "centroid_dist_km": h1_physical["centroid_dist_km"],
            "area_diff_pct": h1_physical["area_diff_pct"],
        },
        "two_source": {
            "bic": h2_gmm["bic"],
            "iou": h2_physical["iou"],
            "centroid_dist_km": h2_physical["centroid_dist_km"],
            "area_diff_pct": h2_physical["area_diff_pct"],
        },
        "decision_factors": decision["factors"],
    }

    def _json_safe(obj):
        """Recursively convert numpy types and Python bools to JSON-serialisable types."""
        if isinstance(obj, dict):
            return {k: _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_json_safe(v) for v in obj]
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    out_json = DATA_PROCESSED / f"{case_id}_spillsplit.json"
    out_json.write_text(json.dumps(_json_safe(result), indent=2))

    # Save diagnostic plot
    save_diagnostic(
        case_id, obs_mask, h1_sim_mask, h2_sim_mask,
        origin_lats, origin_lons,
        h1_gmm["components"], comps, decision["verdict"], DATA_PROCESSED
    )
    print(f"    Saved            : {out_json.name}, {case_id}_spillsplit.png")

    return result


# ── Main ──────────────────────────────────────────────────────────────────────
def main(case_ids=None):
    print(f"\n{'='*64}")
    print(f"Module 4 -- SpillSplit")
    print(f"  H1: One Source Zone   H2: Two Source Zones")
    print(f"  Thresholds: BIC delta>{BIC_DELTA_THRESH}  IoU delta>{IOU_DELTA_THRESH}  Sep>{MIN_SEP_KM}km")
    print(f"{'='*64}")

    ids = case_ids if case_ids else list(CASES.keys())
    all_results = {}

    for cid in ids:
        try:
            all_results[cid] = process_case(cid)
        except FileNotFoundError as e:
            print(f"\n  [{cid.upper()}] SKIPPED — {e}")

    if all_results:
        print(f"\n{'='*64}")
        print("SUMMARY")
        for cid, res in all_results.items():
            print(f"  {cid}: {res['result']}  ({res['confidence']})")
        print(f"\n[OK] Module 4 Definition of Done: SpillSplit completed for {len(all_results)} cases.")
        print(f"{'='*64}\n")

    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, default=None,
                        help="Run one case only (e.g. case_01). Default: all.")
    args = parser.parse_args()
    main(case_ids=[args.case] if args.case else None)
