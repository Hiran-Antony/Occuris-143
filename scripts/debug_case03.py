"""Case 03 ground-truth diagnostic — traces from config through Module 1, 3, and SpillSplit."""
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import CASES

print("=" * 60)
print("CASE 03 — Two-Source Ground Truth Investigation")
print("=" * 60)

# --- 1. Config ground truth
c3 = CASES["case_03"]
print("\n1. CONFIG GROUND TRUTH")
print(f"   Title       : {c3['title']}")
print(f"   Description : {c3['description']}")
print(f"   SAR mask    : {c3['sar_mask']}")
print(f"   Spill bbox  : lat {c3['spill_bbox']['lat_min']}–{c3['spill_bbox']['lat_max']}  lon {c3['spill_bbox']['lon_min']}–{c3['spill_bbox']['lon_max']}")
print(f"   Spill center: lat {c3['spill_center']['lat']}  lon {c3['spill_center']['lon']}")
print(f"   Hindcast    : {c3['release_window_hours']}h")

# --- 2. SAR mask pixel distribution
from PIL import Image
import numpy as np
mask = np.array(Image.open(c3["sar_mask"]).convert("L"))
mask_bin = (mask > 127).astype(np.uint8)
H, W = mask_bin.shape
spill_idx = np.argwhere(mask_bin == 1)
print(f"\n2. SAR MASK (ground truth)")
print(f"   Shape       : {mask_bin.shape}")
print(f"   Spill pixels: {mask_bin.sum()}")

# Convert mask pixels to lat/lon to see if there is spatial bimodality
bbox = c3["spill_bbox"]
pix_lats = bbox["lat_max"] - (spill_idx[:, 0] / H) * (bbox["lat_max"] - bbox["lat_min"])
pix_lons = bbox["lon_min"] + (spill_idx[:, 1] / W) * (bbox["lon_max"] - bbox["lon_min"])
print(f"   Lat range   : {pix_lats.min():.5f} – {pix_lats.max():.5f}  ({(pix_lats.max()-pix_lats.min())*111.32:.2f} km)")
print(f"   Lon range   : {pix_lons.min():.5f} – {pix_lons.max():.5f}  ({(pix_lons.max()-pix_lons.min())*111.32:.2f} km)")
print(f"   Lat std     : {pix_lats.std()*111.32:.3f} km")
print(f"   Lon std     : {pix_lons.std()*111.32:.3f} km")

# Quick bimodality check on latitude distribution
from scipy.stats import skew, kurtosis
print(f"   Lat skewness: {skew(pix_lats):.3f}")
print(f"   Lat kurtosis: {kurtosis(pix_lats):.3f}  (normal=0, bimodal<0)")

# --- 3. Module 3 origin cloud
d3 = json.load(open("data/processed/case_03_drift.json"))
olats = np.array(d3["origin_lats"])
olons = np.array(d3["origin_lons"])
oz = d3["origin_zone"]
print(f"\n3. MODULE 3 ORIGIN CLOUD")
print(f"   N particles : {len(olats)}")
print(f"   Lat range   : {olats.min():.5f} – {olats.max():.5f}  ({(olats.max()-olats.min())*111.32:.2f} km)")
print(f"   Lon range   : {olons.min():.5f} – {olons.max():.5f}  ({(olons.max()-olons.min())*111.32:.2f} km)")
print(f"   Origin center: lat {oz['center_lat']}  lon {oz['center_lon']}")
print(f"   Semi-major  : {oz['semi_major_km']} km")
print(f"   Semi-minor  : {oz['semi_minor_km']} km")
print(f"   Cloud area  : {oz['area_km2']} km2")

# Bimodality check on origin cloud
print(f"   Lat skewness: {skew(olats):.3f}")
print(f"   Lat kurtosis: {kurtosis(olats):.3f}")

# --- 4. SpillSplit output
ss = json.load(open("data/processed/case_03_spillsplit.json"))
print(f"\n4. SPILLSPLIT OUTPUT")
print(f"   Verdict     : {ss['result']}")
print(f"   Confidence  : {ss['confidence']}")
print(f"   Sep (GMM-2) : {ss['source_separation_km']} km")
print(f"   Gate log    : {ss['decision_factors']}")

print()
print("=" * 60)
print("CONCLUSION")
print("The SAR mask bimodality (kurtosis) tells us if the ground-truth")
print("spill has a two-lobed structure that Module 3 should separate.")
print("If kurtosis < -0.5 in the mask but Module 3 produces a tight")
print("unimodal cloud, the collapse happens in Module 3.")
print("=" * 60)
