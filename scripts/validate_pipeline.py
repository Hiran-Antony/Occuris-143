"""
Full Pipeline Validation — Module 2 -> Module 3 -> Module 4
Covers all 8 validation checks as specified.
Produces a single comprehensive terminal report for all 3 cases.
Does NOT push anything. Results printed for human audit first.
"""
import sys, json, math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import CASES, DATA_PROCESSED
from geo_transform import GeoTransform
from detection.geometry import process_case as m2_process
from drift.particle_seed import sample_stratified_seed_points
from drift.velocity_field import VelocityField
from drift.rk4 import RK45DriftEngine
from sklearn.mixture import GaussianMixture
from scipy.stats import kurtosis as scipy_kurtosis

EARTH_R_KM = 6371.0
HAVERSINE = lambda la1, lo1, la2, lo2: 2 * EARTH_R_KM * math.asin(
    math.sqrt(math.sin(math.radians((la2-la1)/2))**2 +
              math.cos(math.radians(la1))*math.cos(math.radians(la2))*
              math.sin(math.radians((lo2-lo1)/2))**2))

SEP = "=" * 68

def banner(txt):
    print(f"\n{SEP}\n  {txt}\n{SEP}")

def section(txt):
    print(f"\n  --- {txt} ---")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1: Module 2  (recalculate geometry with GeoTransform)
# ─────────────────────────────────────────────────────────────────────────────
banner("STEP 1 — MODULE 2: Geometry recalculation with GeoTransform")

m2_results = {}
for cid in CASES:
    m2_process(cid)
    geo_json = json.loads((DATA_PROCESSED / f"{cid}_geometry.json").read_text())
    g = geo_json["geometry"]
    m2_results[cid] = g

    gt = GeoTransform(cid)
    m_row, m_col = gt.metres_per_pixel()
    print(f"\n  [{cid.upper()}]")
    print(f"    [CHECK 1] GeoTransform scale  : {m_row:.1f} m/px (lat)  {m_col:.1f} m/px (lon)")
    print(f"    [CHECK 1] Area (new)          : {g['area_km2']} km2  (from pixel_area_km2)")
    print(f"    [CHECK 1] Area caveat         : {g['area_caveat'][:80]}...")
    print(f"    [CHECK 1] Centroid geo        : {g['centroid_geo']}")
    print(f"    [CHECK 1] Major axis          : {g['major_axis_km']} km")
    print(f"    [CHECK 1] Minor axis          : {g['minor_axis_km']} km")
    print(f"    [CHECK 1] pixel_scale source  : {g.get('pixel_scale',{}).get('transform_source','?')}")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2: Module 3  (seed + backward drift, with per-case validation)
# ─────────────────────────────────────────────────────────────────────────────
banner("STEP 2 — MODULE 3: Seed validation + backward drift")

vf = VelocityField()
engine = RK45DriftEngine(
    velocity_func=vf.get_velocity,
    diffusivity_func=vf.get_eddy_diffusivity
)

m3_results = {}

for cid in CASES:
    hindcast_h = CASES[cid]["release_window_hours"]
    print(f"\n  [{cid.upper()}]  hindcast={hindcast_h}h")

    # -- Seeding
    seed_lats, seed_lons, seed_meta = sample_stratified_seed_points(cid, 50)
    v = seed_meta["pre_seed_validation"]
    print(f"\n    [CHECK 2] Pre-seed validation")
    print(f"      Lat span      : {v['lat_span_km']} km")
    print(f"      Lon span      : {v['lon_span_km']} km")
    print(f"      Geo extent    : {v['geographic_height_km']} x {v['geographic_width_km']} km")
    print(f"      m/px (lat)    : {v['m_per_px_lat']} m")
    print(f"      m/px (lon)    : {v['m_per_px_lon']} m")
    print(f"      Status        : {v['note']}")

    # -- Bimodality check on seeds (do both lobes have particles?)
    seed_kurt = scipy_kurtosis(seed_lats)
    print(f"\n    [CHECK 2] Seed distribution kurtosis (lat): {seed_kurt:.3f}")
    print(f"      (negative kurtosis = flat/bimodal-like, positive = peaked/unimodal)")

    # -- Backward drift with spread tracked at each milestone
    print(f"\n    [CHECK 3] Trajectory spread at time steps:")
    _, _, trajectories = engine.integrate(
        seed_lats=seed_lats, seed_lons=seed_lons,
        duration_hours=hindcast_h, dt_minutes=10.0, backward=True, seed=42
    )
    steps_per_hour = 60 // 10
    for h in [0, 6, 12, 18, 24, hindcast_h]:
        step_idx = min(h * steps_per_hour, len(trajectories) - 1)
        lts, lns = trajectories[step_idx]
        lat_span = (lts.max() - lts.min()) * 111.32
        lon_span = (lns.max() - lns.min()) * 111.32
        print(f"      t={h:2d}h: lat spread={lat_span:.2f} km  lon spread={lon_span:.2f} km")

    # -- Final origin cloud
    final_lats, final_lons = trajectories[-1]
    print(f"\n    [CHECK 4] Origin cloud (final)")
    print(f"      N particles   : {len(final_lats)}")
    print(f"      Lat range     : {final_lats.min():.4f} - {final_lats.max():.4f}  ({(final_lats.max()-final_lats.min())*111.32:.2f} km)")
    print(f"      Lon range     : {final_lons.min():.4f} - {final_lons.max():.4f}  ({(final_lons.max()-final_lons.min())*111.32:.2f} km)")
    print(f"      Kurtosis(lat) : {scipy_kurtosis(final_lats):.3f}  (neg=bimodal-like)")

    # GMM fits on origin cloud
    X = np.column_stack([final_lats, final_lons])
    gmm1 = GaussianMixture(n_components=1, covariance_type="full", random_state=42, n_init=5)
    gmm2 = GaussianMixture(n_components=2, covariance_type="full", random_state=42, n_init=5)
    gmm1.fit(X)
    gmm2.fit(X)
    bic1 = gmm1.bic(X)
    bic2 = gmm2.bic(X)
    sep_km = HAVERSINE(
        float(gmm2.means_[0, 0]), float(gmm2.means_[0, 1]),
        float(gmm2.means_[1, 0]), float(gmm2.means_[1, 1])
    )

    print(f"\n      GMM-1 BIC     : {bic1:.3f}")
    print(f"      GMM-2 BIC     : {bic2:.3f}")
    print(f"      BIC delta     : {bic1-bic2:.3f}  (positive = H2 justified)")
    print(f"      GMM-2 src A   : lat={gmm2.means_[0,0]:.4f}  lon={gmm2.means_[0,1]:.4f}")
    print(f"      GMM-2 src B   : lat={gmm2.means_[1,0]:.4f}  lon={gmm2.means_[1,1]:.4f}")
    print(f"      Source sep    : {sep_km:.3f} km  (gate threshold=5.0 km)")

    m3_results[cid] = {
        "final_lats": final_lats,
        "final_lons": final_lons,
        "bic1": bic1, "bic2": bic2,
        "sep_km": sep_km,
        "gmm1": gmm1, "gmm2": gmm2,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3: Module 4  (SpillSplit gates + forward physics)
# ─────────────────────────────────────────────────────────────────────────────
banner("STEP 3 — MODULE 4: SpillSplit gated validation")

from drift.spillsplit import (
    stability_test, forward_simulate_from_gmm, particles_to_mask,
    compute_physical_fit, MIN_SEP_KM, IOU_DELTA_THRESH, BIC_DELTA_THRESH,
    STABILITY_SEP_FACTOR
)
from detection.geometry import load_predicted_mask, clean_mask

for cid in CASES:
    r3 = m3_results[cid]
    final_lats = r3["final_lats"]
    final_lons = r3["final_lons"]
    sep_km     = r3["sep_km"]
    bic1       = r3["bic1"]
    bic2       = r3["bic2"]
    gmm2       = r3["gmm2"]

    print(f"\n  [{cid.upper()}]")

    # Load observed mask
    raw_mask = load_predicted_mask(cid)
    obs_mask  = clean_mask(raw_mask)

    # [CHECK 5] Gate 1 — Separation
    sep_ok = sep_km >= MIN_SEP_KM
    print(f"\n    [CHECK 5] GATE 1 — Separation: {sep_km:.3f} km vs {MIN_SEP_KM} km threshold")
    print(f"      Result: {'PASS -> continue to Gate 2' if sep_ok else 'FAIL -> One Source Zone'}")

    if not sep_ok:
        print(f"\n    [FINAL]   Verdict: One Source Zone  (Gate 1 fail)")
        print(f"              No further H2 testing will be run.")
        continue

    # [CHECK 6] Gate 2 — Stability
    stab = stability_test(final_lats, final_lons, sep_km)
    print(f"\n    [CHECK 6] GATE 2 — Stability")
    print(f"      Score         : {stab['score']}")
    print(f"      Variation     : {stab['variation_km']} km")
    print(f"      Threshold     : {stab['adaptive_threshold_km']} km  ({STABILITY_SEP_FACTOR}x sep)")
    print(f"      Bootstrap runs: {stab['n_bootstrap_runs']}")
    print(f"      Result        : {stab['note']}")

    stab_ok = stab["stable"]
    if not stab_ok:
        print(f"\n    [FINAL]   Verdict: One Source Zone  (Gate 2 fail — clusters unstable)")
        continue

    # [CHECK 7] Gate 3+4 — Forward physics + BIC
    print(f"\n    [CHECK 7] Forward physical reconstruction")

    # Build GMM component dicts with covariance for seeding
    comps = []
    for i in range(2):
        comps.append({
            "latitude":   float(gmm2.means_[i, 0]),
            "longitude":  float(gmm2.means_[i, 1]),
            "weight":     float(gmm2.weights_[i]),
            "covariance": gmm2.covariances_[i].tolist(),
        })

    # H1 forward
    h1_comp = {
        "latitude":   float(r3["gmm1"].means_[0, 0]),
        "longitude":  float(r3["gmm1"].means_[0, 1]),
        "weight":     1.0,
        "covariance": r3["gmm1"].covariances_[0].tolist(),
    }
    h1_lats, h1_lons = forward_simulate_from_gmm(h1_comp, 30, vf, seed=42)
    h1_mask = particles_to_mask(h1_lats, h1_lons, cid)
    h1_fit  = compute_physical_fit(obs_mask, h1_mask, cid)

    # H2 forward
    h2_all_lats, h2_all_lons = np.array([]), np.array([])
    for i, comp in enumerate(comps):
        fl, flo = forward_simulate_from_gmm(comp, 16, vf, seed=42 + i)
        h2_all_lats = np.concatenate([h2_all_lats, fl])
        h2_all_lons = np.concatenate([h2_all_lons, flo])
    h2_mask = particles_to_mask(h2_all_lats, h2_all_lons, cid)
    h2_fit  = compute_physical_fit(obs_mask, h2_mask, cid)

    iou_delta   = h2_fit["iou"] - h1_fit["iou"]
    bic_delta   = bic1 - bic2
    physics_ok  = iou_delta >= IOU_DELTA_THRESH
    bic_ok      = bic_delta >= BIC_DELTA_THRESH

    print(f"      H1 IoU        : {h1_fit['iou']}   centroid dist: {h1_fit['centroid_dist_km']} km")
    print(f"      H2 IoU        : {h2_fit['iou']}   centroid dist: {h2_fit['centroid_dist_km']} km")
    print(f"      IoU delta     : {iou_delta:.4f}  (threshold={IOU_DELTA_THRESH})")
    print(f"      BIC delta     : {bic_delta:.3f}  (threshold={BIC_DELTA_THRESH})")
    print(f"      Gate 3 (phys) : {'PASS' if physics_ok else 'FAIL'}")
    print(f"      Gate 4 (BIC)  : {'PASS' if bic_ok else 'FAIL'}")

    # [CHECK 8] Final verdict
    if not physics_ok:
        verdict = "One Source Zone"
        reason  = "Gate 3 fail: H2 does not materially improve physical reconstruction"
    elif bic_ok:
        verdict = "Two Source Zones"
        reason  = "All gates passed"
    else:
        verdict = "Inconclusive"
        reason  = "Physics supports H2 but BIC penalty insufficient (carry INCONCLUSIVE flag)"

    print(f"\n    [CHECK 8] FINAL VERDICT: {verdict}")
    print(f"              Reason: {reason}")


banner("VALIDATION COMPLETE — awaiting human audit before push")
print("""
  Summary of new values vs old values:
  
  Module 2 area scale:
    Old: 10 m/px  (SAR sensor resolution — wrong for 256px image)
    New: ~609-696 m/px  (spill_bbox / 256 — correct geographic scale)
    
  Module 3 seed span:
    Old: ~2.5 km  (all 50 particles in tiny patch)
    New: ~153-165 km  (particles span actual geographic spill extent)
    
  SpillSplit decision: gated sequential (not voting)
    Separation -> Stability -> Physics -> BIC
    
  Inconclusive is a genuine third verdict — not silently One Source.
""")
