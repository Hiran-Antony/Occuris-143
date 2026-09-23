# Module 9 Phase 3: FastAPI Bridge Integration

- [ ] Inspect M1-M8 actual JSON outputs (e.g. `case_01_bundle.json`, `case_01_geometry.json`, `case_01_m7.json`) and python schemas (`src/investigation/schemas.py`).
- [ ] Initialize FastAPI application in `src/api/main.py`.
- [ ] Implement Dashboard APIs (`/api/dashboard/summary`, `/api/cases`, `/api/cases/{case_id}`).
- [ ] Implement Geospatial/Spill APIs (`/api/cases/{case_id}/map`, `.../spill`, `.../origin-zone`, `.../drift`).
- [ ] Implement Maritime APIs (`/api/cases/{case_id}/vessels`, `.../track`, `.../gateway-events`).
- [ ] Implement Investigation APIs (`/api/cases/{case_id}/investigation`, `.../candidates`, `.../evidence-graph`).
- [ ] Update frontend `src/api/client.ts` to match the new case-based REST endpoints.
- [x] Update frontend `RegionalMonitoring.tsx` to fetch cases dynamically and fly bounds to the selected case.
- [x] Update frontend forensic pages to replace terminology (e.g., "PRIMARY SUSPECT TRACK" -> "SELECTED CANDIDATE TRACK") and ensure synthetic labels.
- [x] Start backend and verify end-to-end rendering on the UI.
