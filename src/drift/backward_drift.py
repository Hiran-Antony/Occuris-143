"""
Module 3 — Backward Drift Reconstruction (Hindcasting)
Simulates where an oil spill originated by running particles backward
through synthetic Arabian Sea wind + current fields.

Uses a pure-numpy particle advection engine (OceanParcels replacement)
that is self-contained and offline-safe for the MVP demo.

Usage:
  python src/drift/backward_drift.py
  python src/drift/backward_drift.py --case case_01
"""
import sys, json, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.ndimage import zoom
from PIL import Image

from config import (
    CASES, DATA_PROCESSED, OCEAN_DIR, WIND_DIR,
    N_PARTICLES, DRIFT_HOURS, WIND_LEEWAY, PIXEL_SCALE_M if hasattr(__import__("config"), "PIXEL_SCALE_M") else None
)

# Pixel scale — fall back if not in config
try:
    from config import PIXEL_SCALE_M
except ImportError:
    PIXEL_SCALE_M = 10.0

M_PER_DEG_LAT = 111_320.0   # metres per degree latitude (fixed)


# ── Field loader ───────────────────────────────────────────────────────────────

def load_fields():
    curr = np.load(OCEAN_DIR / "current_arabian_sea.npz")
    wind = np.load(WIND_DIR  / "wind_arabian_sea.npz")
    return curr, wind


def interpolate_velocity(lat, lon, field, lats, lons) -> tuple:
    """Bilinear interpolation of U, V at a given lat/lon."""
    lat = np.clip(lat, lats[0], lats[-1])
    lon = np.clip(lon, lons[0], lons[-1])

    i0 = np.searchsorted(lats, lat) - 1
    j0 = np.searchsorted(lons, lon) - 1
    i0 = int(np.clip(i0, 0, len(lats) - 2))
    j0 = int(np.clip(j0, 0, len(lons) - 2))

    dy = (lat - lats[i0]) / (lats[i0 + 1] - lats[i0] + 1e-10)
    dx = (lon - lons[j0]) / (lons[j0 + 1] - lons[j0] + 1e-10)

    U = (field["U"][i0,   j0]   * (1 - dy) * (1 - dx) +
         field["U"][i0+1, j0]   * dy       * (1 - dx) +
         field["U"][i0,   j0+1] * (1 - dy) * dx       +
         field["U"][i0+1, j0+1] * dy       * dx)
    V = (field["V"][i0,   j0]   * (1 - dy) * (1 - dx) +
         field["V"][i0+1, j0]   * dy       * (1 - dx) +
         field["V"][i0,   j0+1] * (1 - dy) * dx       +
         field["V"][i0+1, j0+1] * dy       * dx)
    return float(U), float(V)


# ── Particle advection ─────────────────────────────────────────────────────────

def advect_particles(seed_lats: np.ndarray, seed_lons: np.ndarray,
                     curr_field: dict, wind_field: dict,
                     hours: int, direction: int = -1,
                     dt_min: int = 30) -> tuple:
    """
    Advect N particles for `hours` hours.
    direction = -1 → backward (hindcast)
    direction = +1 → forward  (forecast)
    Returns final (lats, lons), trajectory list.
    """
    lats_g = curr_field["lats"]
    lons_g = curr_field["lons"]
    n_steps = int(hours * 60 / dt_min)
    dt_s    = dt_min * 60 * direction   # seconds per step, sign sets direction

    p_lat = seed_lats.copy()
    p_lon = seed_lons.copy()
    trajectories = [(p_lat.copy(), p_lon.copy())]

    for _ in range(n_steps):
        for i in range(len(p_lat)):
            u_c, v_c = interpolate_velocity(p_lat[i], p_lon[i],
                                            {"U": curr_field["U"], "V": curr_field["V"]},
                                            lats_g, lons_g)
            u_w, v_w = interpolate_velocity(p_lat[i], p_lon[i],
                                            {"U": wind_field["U"], "V": wind_field["V"]},
                                            lats_g, lons_g)
            # total velocity: current + wind leeway
            u_total = u_c + WIND_LEEWAY * u_w
            v_total = v_c + WIND_LEEWAY * v_w

            # convert m/s → deg/s
            m_per_deg_lon = M_PER_DEG_LAT * np.cos(np.radians(p_lat[i]))
            p_lat[i] += v_total * dt_s / M_PER_DEG_LAT
            p_lon[i] += u_total * dt_s / (m_per_deg_lon + 1e-10)

        trajectories.append((p_lat.copy(), p_lon.copy()))

    return p_lat, p_lon, trajectories


# ── Seed points from mask ──────────────────────────────────────────────────────

def sample_seed_points(case_id: str, n: int = N_PARTICLES) -> tuple:
    """Sample N points uniformly from the spill mask, in lat/lon."""
    mask_path = Path(CASES[case_id]["sar_mask"])
    mask = np.array(Image.open(mask_path).convert("L"))
    mask = (mask > 127).astype(np.uint8)

    spill_idx = np.argwhere(mask == 1)
    if len(spill_idx) == 0:
        raise ValueError(f"No spill pixels in mask for {case_id}")

    rng = np.random.default_rng(42)
    chosen = spill_idx[rng.choice(len(spill_idx), min(n, len(spill_idx)), replace=False)]
    H, W   = mask.shape
    bbox   = CASES[case_id]["spill_bbox"]

    seed_lats = bbox["lat_max"] - (chosen[:, 0] / H) * (bbox["lat_max"] - bbox["lat_min"])
    seed_lons = bbox["lon_min"] + (chosen[:, 1] / W) * (bbox["lon_max"] - bbox["lon_min"])
    return seed_lats, seed_lons


# ── Covariance ellipse ─────────────────────────────────────────────────────────

def fit_uncertainty_ellipse(lats: np.ndarray, lons: np.ndarray) -> dict:
    """Fit a 2-sigma covariance ellipse to the origin point cloud."""
    pts  = np.column_stack([lons, lats])
    cov  = np.cov(pts.T)
    evals, evecs = np.linalg.eigh(cov)
    order = evals.argsort()[::-1]
    evals, evecs = evals[order], evecs[:, order]

    angle_deg = float(np.degrees(np.arctan2(evecs[1, 0], evecs[0, 0])))
    # 2-sigma ellipse (95 % confidence)
    a_deg = float(2 * np.sqrt(evals[0]))   # semi-major in degrees
    b_deg = float(2 * np.sqrt(evals[1]))   # semi-minor in degrees
    a_km  = a_deg * M_PER_DEG_LAT / 1000.0
    b_km  = b_deg * M_PER_DEG_LAT / 1000.0

    return {
        "center_lat":     round(float(lats.mean()), 5),
        "center_lon":     round(float(lons.mean()), 5),
        "semi_major_km":  round(a_km, 3),
        "semi_minor_km":  round(b_km, 3),
        "angle_deg":      round(angle_deg, 2),
        "a_deg":          round(a_deg, 6),
        "b_deg":          round(b_deg, 6),
    }


# ── Release time window ────────────────────────────────────────────────────────

def compute_release_window(case_id: str, drift_hours: int) -> dict:
    import datetime
    sar_ts = CASES[case_id]["sar_timestamp"]
    sar_dt = datetime.datetime.strptime(sar_ts, "%Y-%m-%dT%H:%M:%SZ")
    release_end   = sar_dt - datetime.timedelta(hours=1)
    release_start = sar_dt - datetime.timedelta(hours=drift_hours + 6)
    return {
        "release_start": release_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_end":   release_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours":  drift_hours + 5,
    }


# ── Plot ───────────────────────────────────────────────────────────────────────

def plot_drift(case_id: str, seed_lats, seed_lons,
               origin_lats, origin_lons, trajectories,
               ellipse: dict, release_window: dict, out_dir: Path):
    fig, ax = plt.subplots(figsize=(10, 8))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1225")

    # draw trajectories (subsample for clarity)
    n_draw = min(20, len(seed_lats))
    for i in range(0, len(seed_lats), max(1, len(seed_lats) // n_draw)):
        traj_lats = [step[0][i] for step in trajectories]
        traj_lons = [step[1][i] for step in trajectories]
        ax.plot(traj_lons, traj_lats, color="#4a9eff", alpha=0.25, linewidth=0.7)

    # spill seed points (observation)
    ax.scatter(seed_lons, seed_lats, c="#ff6b35", s=12, zorder=5,
               label="Spill mask (SAR observation)")

    # origin point cloud
    ax.scatter(origin_lons, origin_lats, c="#00e676", s=14, alpha=0.6, zorder=6,
               label=f"Origin particles (n={len(origin_lats)})")

    # uncertainty ellipse
    from matplotlib.patches import Ellipse
    e = Ellipse(xy=(ellipse["center_lon"], ellipse["center_lat"]),
                width=ellipse["a_deg"] * 2, height=ellipse["b_deg"] * 2,
                angle=ellipse["angle_deg"],
                edgecolor="#ffe066", facecolor="none", linewidth=2,
                linestyle="--", zorder=7, label="2-sigma origin zone")
    ax.add_patch(e)
    ax.plot(ellipse["center_lon"], ellipse["center_lat"], "y*", markersize=14,
            zorder=8, label="Origin centroid")

    # labels
    ax.set_xlabel("Longitude (E)", color="white")
    ax.set_ylabel("Latitude (N)",  color="white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")

    title = (f"Occuris — {case_id.replace('_',' ').title()} | Backward Drift\n"
             f"Origin: lat={ellipse['center_lat']}  lon={ellipse['center_lon']}  "
             f"a={ellipse['semi_major_km']}km  b={ellipse['semi_minor_km']}km\n"
             f"Release window: {release_window['release_start']} → {release_window['release_end']}")
    ax.set_title(title, color="white", fontsize=9, pad=10)
    ax.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{case_id}_backward_drift.png"
    plt.savefig(out_path, bbox_inches="tight", dpi=130, facecolor=fig.get_facecolor())
    plt.close()
    return out_path


# ── Main ───────────────────────────────────────────────────────────────────────

def run_backward_drift(case_ids=None) -> dict:
    curr_raw = np.load(OCEAN_DIR / "current_arabian_sea.npz")
    wind_raw = np.load(WIND_DIR  / "wind_arabian_sea.npz")
    curr_field = {k: curr_raw[k] for k in curr_raw.files}
    wind_field = {k: wind_raw[k] for k in wind_raw.files}

    ids = case_ids if case_ids else list(CASES.keys())
    results = {}

    print(f"\n{'='*62}")
    print(f"Module 3 -- Backward Drift Reconstruction")
    print(f"{'='*62}")
    print(f"  Particles: {N_PARTICLES}  Duration: {DRIFT_HOURS}h  "
          f"Wind leeway: {WIND_LEEWAY*100:.0f}%")

    for case_id in ids:
        print(f"\n  Processing {case_id}...")
        seed_lats, seed_lons = sample_seed_points(case_id, N_PARTICLES)
        origin_lats, origin_lons, trajs = advect_particles(
            seed_lats, seed_lons, curr_field, wind_field,
            hours=CASES[case_id]["release_window_hours"], direction=-1
        )
        ellipse  = fit_uncertainty_ellipse(origin_lats, origin_lons)
        rel_win  = compute_release_window(case_id, CASES[case_id]["release_window_hours"])
        out_path = plot_drift(case_id, seed_lats, seed_lons,
                              origin_lats, origin_lons, trajs,
                              ellipse, rel_win, DATA_PROCESSED)

        results[case_id] = {
            "origin_ellipse":   ellipse,
            "release_window":   rel_win,
            "origin_lats":      origin_lats.tolist(),
            "origin_lons":      origin_lons.tolist(),
            "plot":             str(out_path),
        }

        # Save JSON
        (DATA_PROCESSED / f"{case_id}_drift.json").write_text(
            json.dumps({k: v for k, v in results[case_id].items()
                        if k not in ("origin_lats","origin_lons")}, indent=2))

        print(f"    Origin centre  : lat={ellipse['center_lat']}  lon={ellipse['center_lon']}")
        print(f"    Ellipse        : a={ellipse['semi_major_km']}km  b={ellipse['semi_minor_km']}km  "
              f"angle={ellipse['angle_deg']}deg")
        print(f"    Release window : {rel_win['release_start']} --> {rel_win['release_end']}")
        print(f"    Plot saved     : {out_path}")

    print(f"\n[OK] Module 3 Definition of Done: origin ellipse + release window for all {len(ids)} cases.")
    print(f"{'='*62}\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, default=None)
    args = parser.parse_args()
    run_backward_drift(case_ids=[args.case] if args.case else None)
