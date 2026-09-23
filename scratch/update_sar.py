import re

# Update main.py
with open('src/api/main.py', 'r', encoding='utf-8') as f:
    main_code = f.read()

# Add static file mounts
main_code = main_code.replace('from fastapi import FastAPI, HTTPException', 'from fastapi import FastAPI, HTTPException\nfrom fastapi.staticfiles import StaticFiles')
main_code = main_code.replace('app = FastAPI(title="Occuris API Bridge")', 'app = FastAPI(title="Occuris API Bridge")\napp.mount("/sar", StaticFiles(directory="data/raw/sar"), name="sar")\napp.mount("/masks", StaticFiles(directory="data/processed"), name="masks")')

# Update CASES to include sar paths
main_code = main_code.replace('{"id": "case_01", "name": "Al-Mahra Corridor", "region": "Arabian Sea", "status": "ACTIVE"}', '{"id": "case_01", "name": "Al-Mahra Corridor", "region": "Arabian Sea", "status": "ACTIVE", "sar_image_path": "sar_01.png", "mask_path": "case_01_pred_mask.png"}')
main_code = main_code.replace('{"id": "case_02", "name": "Lakshadweep Passage", "region": "Arabian Sea", "status": "ACTIVE"}', '{"id": "case_02", "name": "Lakshadweep Passage", "region": "Arabian Sea", "status": "ACTIVE", "sar_image_path": "sar_02.png", "mask_path": "case_02_pred_mask.png"}')
main_code = main_code.replace('{"id": "case_03", "name": "Oman Basin", "region": "Arabian Sea", "status": "ACTIVE"}', '{"id": "case_03", "name": "Oman Basin", "region": "Arabian Sea", "status": "ACTIVE", "sar_image_path": "sar_03.png", "mask_path": "case_03_pred_mask.png"}')

with open('src/api/main.py', 'w', encoding='utf-8') as f:
    f.write(main_code)
print('Updated main.py')

# Update ForensicInvestigation.tsx
with open('frontend/src/pages/ForensicInvestigation.tsx', 'r', encoding='utf-8') as f:
    ui_code = f.read()

ui_code = ui_code.replace('http://localhost:8000/sar/', 'http://localhost:8080/sar/')
ui_code = ui_code.replace('http://localhost:8000/masks/', 'http://localhost:8080/masks/')

with open('frontend/src/pages/ForensicInvestigation.tsx', 'w', encoding='utf-8') as f:
    f.write(ui_code)
print('Updated ForensicInvestigation.tsx')
