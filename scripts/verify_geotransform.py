import sys
sys.path.insert(0, 'src')
from geo_transform import GeoTransform
from drift.particle_seed import sample_stratified_seed_points

print("=== GeoTransform audit across all cases ===")
for cid in ['case_01', 'case_02', 'case_03']:
    gt = GeoTransform(cid)
    gt.print_summary()
    print()

print("=== Pre-seed validation ===")
for cid in ['case_01', 'case_02', 'case_03']:
    lats, lons, meta = sample_stratified_seed_points(cid, 50)
    v = meta['pre_seed_validation']
    print(f"  {cid}: lat_span={v['lat_span_km']} km  lon_span={v['lon_span_km']} km  -> {v['note']}")
