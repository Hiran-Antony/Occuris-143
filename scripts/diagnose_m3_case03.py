"""
Module 3 Diagnostic — Case 03 Two-Source Convergence Investigation
Covers all five diagnostic points:
  1. Particle seeding  — are seeds distributed across both lobes?
  2. Flow field        — spatial variation vs flat field?
  3. Drift integration — per-particle displacement magnitude and direction
  4. Time window       — does drift duration drive convergence?
  5. Coordinate scale  — is PIXEL_SCALE_M compressing the seeded positions?
Outputs a multi-panel diagnostic PNG.
"""
import sys, json, math
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import CASES, DATA_PROCESSED, OCEAN_DIR, WIND_DIR, PIXEL_SCALE_M, N_PARTICLES
from drift.velocity_field import VelocityField
from drift.rk4 import RK45DriftEngine
from drift.particle_seed import sample_stratified_seed_points

CASE_ID = "case_03"
M_PER_DEG = 111_320.0

# ── 1. Load seed points and show their geographic spread ──────────────────────
print("\n[1] PARTICLE SEEDING")
seed_lats, seed_lons, meta = sample_stratified_seed_points(CASE_ID, N_PARTICLES)
print(f"    N seeds       : {len(seed_lats)}")
print(f"    Lat range     : {seed_lats.min():.5f} – {seed_lats.max():.5f}")
print(f"    Lon range     : {seed_lons.min():.5f} – {seed_lons.max():.5f}")
lat_span_km = (seed_lats.max() - seed_lats.min()) * 111.32
lon_span_km = (seed_lons.max() - seed_lons.min()) * 111.32
print(f"    Lat span      : {lat_span_km:.3f} km")
print(f"    Lon span      : {lon_span_km:.3f} km")
print(f"    PIXEL_SCALE_M : {PIXEL_SCALE_M} m/px  — mask is 256×256 px")
print(f"    Expected span : {256 * PIXEL_SCALE_M / 1000:.2f} km max (256px × {PIXEL_SCALE_M}m)")

# ── 2. Flow field spatial variation ───────────────────────────────────────────
print("\n[2] FLOW FIELD SPATIAL VARIATION")
vf = VelocityField()
# Sample velocities at seed positions
u_net = np.array([vf.get_velocity(lat, lon)[0] for lat, lon in zip(seed_lats, seed_lons)])
v_net = np.array([vf.get_velocity(lat, lon)[1] for lat, lon in zip(seed_lats, seed_lons)])
speeds = np.sqrt(u_net**2 + v_net**2)
print(f"    Net speed range   : {speeds.min():.4f} – {speeds.max():.4f} m/s")
print(f"    Net speed std     : {speeds.std():.6f} m/s")
print(f"    U range           : {u_net.min():.4f} – {u_net.max():.4f} m/s")
print(f"    V range           : {v_net.min():.4f} – {v_net.max():.4f} m/s")
print(f"    U std             : {u_net.std():.6f} m/s")
print(f"    V std             : {v_net.std():.6f} m/s")
field_is_flat = speeds.std() < 0.001
print(f"    Field effectively flat? {'YES — all particles see same velocity' if field_is_flat else 'NO — spatial variation present'}")

# ── 3. Drift integration — per-particle displacement ─────────────────────────
print("\n[3] DRIFT INTEGRATION — PER-PARTICLE DISPLACEMENT")
hindcast_h = CASES[CASE_ID]["release_window_hours"]
engine = RK45DriftEngine(
    velocity_func=vf.get_velocity,
    diffusivity_func=vf.get_eddy_diffusivity
)
final_lats, final_lons, trajectories = engine.integrate(
    seed_lats=seed_lats, seed_lons=seed_lons,
    duration_hours=hindcast_h, dt_minutes=10.0, backward=True, seed=42
)

# Displacement for each particle
disp_km = np.array([
    math.sqrt(
        ((final_lats[i] - seed_lats[i]) * M_PER_DEG / 1000) ** 2 +
        ((final_lons[i] - seed_lons[i]) * M_PER_DEG * math.cos(math.radians(seed_lats[i])) / 1000) ** 2
    )
    for i in range(len(seed_lats))
])
print(f"    Hindcast hours    : {hindcast_h}h")
print(f"    Displacement range: {disp_km.min():.3f} – {disp_km.max():.3f} km")
print(f"    Displacement mean : {disp_km.mean():.3f} km")
print(f"    Displacement std  : {disp_km.std():.3f} km")
print(f"    Final lat range   : {final_lats.min():.5f} – {final_lats.max():.5f}  ({(final_lats.max()-final_lats.min())*111.32:.3f} km)")
print(f"    Final lon range   : {final_lons.min():.5f} – {final_lons.max():.5f}  ({(final_lons.max()-final_lons.min())*111.32:.3f} km)")

# ── 4. Time window sensitivity ────────────────────────────────────────────────
print("\n[4] TIME WINDOW SENSITIVITY")
for test_h in [6, 12, 18, hindcast_h]:
    fl, flo, _ = engine.integrate(
        seed_lats=seed_lats, seed_lons=seed_lons,
        duration_hours=test_h, dt_minutes=10.0, backward=True, seed=42
    )
    span = (fl.max() - fl.min()) * 111.32
    print(f"    At {test_h:2d}h backward: final lat spread = {span:.3f} km  (origin lat range)")

# ── 5. Coordinate scale check ─────────────────────────────────────────────────
print("\n[5] COORDINATE SCALE")
print(f"    PIXEL_SCALE_M = {PIXEL_SCALE_M} m/px")
print(f"    At {PIXEL_SCALE_M} m/px, 256×256 image covers {256*PIXEL_SCALE_M/1000:.2f} × {256*PIXEL_SCALE_M/1000:.2f} km")
print(f"    This is the seed domain. Backward drift of ~{disp_km.mean():.1f} km moves ALL")
print(f"    particles by nearly the SAME vector, so relative spacing is preserved but")
print(f"    origin separation cannot exceed seed separation ({lat_span_km:.2f} km).")
print(f"    => ROOT CAUSE: seed spatial spread ({lat_span_km:.2f} km) is much smaller than")
print(f"       what PIXEL_SCALE_M implies at the bbox scale (177 km from config bbox).")

# ── Diagnostic Plot ───────────────────────────────────────────────────────────
print("\n[PLOT] Generating diagnostic...")

fig = plt.figure(figsize=(24, 7))
fig.patch.set_facecolor("#0d1117")
gs = gridspec.GridSpec(1, 5, figure=fig, wspace=0.3)
axes = [fig.add_subplot(gs[0, i]) for i in range(5)]
for ax in axes:
    ax.set_facecolor("#0d1225")
    ax.tick_params(colors="white", labelsize=7)
    for sp in ax.spines.values():
        sp.set_edgecolor("#333")

# Panel 0: Ground truth SAR mask
mask_img = np.array(Image.open(CASES[CASE_ID]["sar_mask"]).convert("L"))
axes[0].imshow(mask_img, cmap="magma", origin="upper")
axes[0].set_title("GT SAR Mask\nkurtosis=-1.04 (bimodal?)", color="white", fontsize=8)
axes[0].axis("off")

# Panel 1: Seed positions geographic
scatter_c = plt.cm.plasma(np.linspace(0, 1, len(seed_lats)))
axes[1].scatter(seed_lons, seed_lats, c=scatter_c, s=15, alpha=0.8)
axes[1].set_title(f"Seed Points\nSpan: {lat_span_km:.2f}km × {lon_span_km:.2f}km", color="white", fontsize=8)
axes[1].set_xlabel("Lon", color="white", fontsize=7)
axes[1].set_ylabel("Lat", color="white", fontsize=7)

# Panel 2: Flow field at seed positions (quiver)
axes[2].scatter(seed_lons, seed_lats, c="#4a9eff", s=10, alpha=0.5, zorder=3)
axes[2].quiver(seed_lons[::5], seed_lats[::5], u_net[::5], v_net[::5],
               color="#00e676", scale=None, scale_units="xy", angles="xy", width=0.003)
axes[2].set_title(f"Net Velocity at Seeds\nSpd std={speeds.std():.5f} m/s", color="white", fontsize=8)
axes[2].set_xlabel("Lon", color="white", fontsize=7)

# Panel 3: Backward drift trajectories (subsample 15)
step = max(1, len(seed_lats) // 15)
for i in range(0, len(seed_lats), step):
    traj_lats = [t[0][i] for t in trajectories]
    traj_lons = [t[1][i] for t in trajectories]
    axes[3].plot(traj_lons, traj_lats, color="#4a9eff", alpha=0.3, linewidth=0.7)
axes[3].scatter(seed_lons, seed_lats, c="#ff6b35", s=12, zorder=5, label="Seeds")
axes[3].scatter(final_lons, final_lats, c="#00e676", s=12, zorder=6, label="Origins")
axes[3].legend(facecolor="#1a1a2e", labelcolor="white", fontsize=6)
axes[3].set_title(f"Backward Trajectories\n{hindcast_h}h hindcast", color="white", fontsize=8)
axes[3].set_xlabel("Lon", color="white", fontsize=7)

# Panel 4: Displacement histogram
axes[4].hist(disp_km, bins=12, color="#ffd740", edgecolor="#1a1a2e", alpha=0.85)
axes[4].set_title(f"Displacement Distribution\nmean={disp_km.mean():.2f}km std={disp_km.std():.2f}km", color="white", fontsize=8)
axes[4].set_xlabel("Displacement (km)", color="white", fontsize=7)
axes[4].set_ylabel("Count", color="white", fontsize=7)

fig.suptitle(
    f"Occuris — Module 3 Diagnostic — {CASE_ID} — Two-Source Convergence Investigation",
    color="white", fontsize=10, y=1.01
)
plt.tight_layout()
out_path = DATA_PROCESSED / f"{CASE_ID}_m3_diagnostic.png"
plt.savefig(out_path, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"    Saved: {out_path}")
print("\n[DONE]")
