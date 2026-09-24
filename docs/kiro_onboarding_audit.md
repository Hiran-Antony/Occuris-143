# Kiro Onboarding Audit Report — Occuris v1.0.0

**Date**: 2026-09-24  
**Auditor**: Kiro AI Agent  
**Purpose**: Complete repository exploration and reality check before Module 8–10 implementation  
**Status**: ⚠️ **CRITICAL DISCREPANCIES FOUND**

---

## 1. Repository Structure Inventory

### 1.1 Module File Mapping

| Module | Status | Primary Location | Key Files | Contract |
|--------|--------|------------------|-----------|----------|
| **M0: Data Foundation** | ✅ DONE | `data/raw/` | `ais/ais_sample.csv`, `sar/*.png`, `ocean/*.npz` | SQLite schema in code |
| **M1: SAR Detection** | ✅ DONE | `src/detection/` | `infer.py`, `train.py`, `geometry.py`, `dataset.py` | None (outputs mask + geometry) |
| **M2: Look-Alike Verification** | ✅ DONE | `src/detection/geometry.py` | Embedded in detection module | SpillGeometry schema |
| **M3: Backward Hindcast** | ✅ DONE | `src/drift/` | `backward_drift.py`, `origin_zone.py`, `rk4.py`, `velocity_field.py` | None (outputs zone + window) |
| **M4: SpillSplit** | ✅ DONE | `src/drift/spillsplit.py` | Single file in drift module | None (outputs hypothesis + BIC) |
| **M5: Maritime Memory** | ✅ DONE (v5.1) | `src/ais/` | 13 files; `maritime_memory.py`, `gateways.py`, `crossing.py`, `behaviour.py`, `dna.py`, `collective.py`, `dark_path.py`, `audit.py` | **EvidenceBundleV1** (frozen) |
| **M6: AIS Verification** | ✅ DONE | `src/verification/` | `pipeline.py`, `window_resolver.py`, `continuity_analyzer.py`, `kinematic_engine.py`, `reachability_engine.py`, `dark_path_validator.py`, `state_classifier.py` | **Module6VerificationBundleV1** (frozen) |
| **M7: Counterfactual** | ✅ DONE | `src/counterfactual/` | `counterfactual_engine.py`, `release_sampler.py`, `transport.py`, `metrics.py`, `baseline.py`, `particle_initializer.py`, `rasterizer.py`, `sensitivity.py`, `candidate_selector.py`, `uncertainty.py`, `validation.py` | None (outputs match score + evidence) |
| **M8: Forensic Ranking** | ⚠️ **PARTIAL** | `src/investigation/` | `candidate_evidence.py`, `spatial_analysis.py`, `temporal_analysis.py`, `evidence_fusion.py` — **NO odds-form Bayes, NO sensitivity.py, NO hypotheses.py, NO planner.py, NO RankingBundleV1** | ❌ **MISSING** |
| **M9: Dashboard** | ✅ PARTIAL | `frontend/` | React + TypeScript + Vite + MapLibre **present and working** — tabs exist but **incomplete** (no WeasyPrint PDF, no ledger verify UI, no analyst decision buttons) | N/A |
| **M10: Integration** | ❌ **NOT STARTED** | N/A | **No demo pack, no offline mode, no `scripts/run_demo.sh`, no `docs/demo_narration.md`** | N/A |

### 1.2 Additional Modules Found (not in spec)
- `src/attribution/` — **EMPTY** (only `__init__.py`)

---

## 2. Frozen Contract Verification

### 2.1 Contracts Found

| Contract | Location | Schema Version | Ledger Integration | Tests |
|----------|----------|----------------|-------------------|-------|
| **EvidenceBundleV1** | `src/ais/schemas.py:439` | `schema_version: "1.0"` | ✅ Yes (M5 artifacts) | ✅ `tests/contract/test_evidence_bundle.py` |
| **Module6VerificationBundleV1** | `src/ais/schemas.py:667` | `schema_version: "v6.0"` | ✅ Yes (M6 artifacts) | ✅ Snapshot tests exist |
| **RankingBundleV1** | ❌ **NOT FOUND** | N/A | ❌ Not integrated | ❌ Does not exist |
| **InvestigationReportBundleV1** | `src/investigation/schemas.py` | No version field | ❌ **Not in ledger** | ❌ No contract tests |

### 2.2 RunManifests Table
- ✅ Exists in `src/ais/schemas.py:463`
- ✅ Schema includes: `run_id`, `case_id`, `input_csv_hash`, `region_yaml_hash`, `pipeline_params_hash`, `random_seed`, `completed_at`, `module_versions`

### 2.3 Merkle Audit Chain
- ✅ Single chain confirmed in `src/ais/audit.py`
- ✅ Extends for M5 (`GATEWAY_CROSSING`, `JOURNEY_COMPLETE`, etc.) and M6 (`VERIFICATION_ARTIFACT`)
- ⚠️ **M8 extension not implemented** — no `RANKING_ARTIFACT` event type

---

## 3. Test Suite Status

### 3.1 Current State
```
Total tests collected: 177
Passing: 176
Failing: 1
```

**Failing Test**: `tests/integration/test_investigation_pipeline.py::test_investigation_pipeline`  
**Error**: `AttributeError: 'Module6VerificationBundleV1' object has no attribute 'status'`  
**Root Cause**: Investigation module expects a `status` field that doesn't exist in the frozen contract

### 3.2 Coverage Analysis
- ❌ Coverage run timed out after 3 minutes (likely infinite loop or hang)
- Last successful coverage from DoD reports:
  - M5 (`src/ais/`): **93% statement coverage** (58 tests)
  - M6 (`src/verification/`): **92% statement coverage** (120 tests)

### 3.3 Test Organization
```
tests/
├── contract/         # Frozen schema snapshot tests
│   └── test_evidence_bundle.py
├── integration/      # End-to-end pipeline tests
│   ├── test_full_pipeline.py (M5)
│   ├── test_verification_pipeline.py (M6)
│   └── test_investigation_pipeline.py (M8 PARTIAL — FAILING)
├── integrity/        # Guard tests (language, imports)
│   └── test_guards.py
├── property/         # Invariant tests (Hypothesis)
│   └── test_invariants.py
├── unit/            # Module-specific unit tests
│   ├── test_audit.py
│   ├── test_behaviour.py
│   ├── test_collective.py
│   ├── test_crossing.py
│   ├── test_dark_path.py
│   ├── test_delay_analysis.py
│   ├── test_dna.py
│   ├── test_ingest.py
│   ├── test_maritime_memory.py
│   ├── test_track_builder.py
│   └── test_traffic.py
└── test_module5.py   # Legacy M5 tests
```

---

## 4. Configuration Files

### 4.1 Config Inventory

| File | Purpose | Status | Magic Numbers |
|------|---------|--------|---------------|
| `config.json` | SegFormer-B0 model architecture | ✅ Complete | None (Hugging Face standard) |
| `config/region.yaml` | M5 gateways, thresholds, baselines | ✅ Complete | 0 (all externalized per A3) |
| `config/verification.yaml` | M6 EKF, Bayes LR, reachability | ✅ Complete | 0 (all documented) |
| `config/counterfactual.yaml` | M7 simulation params | ✅ Exists | Need to verify |
| **`config/ranking.yaml`** | **M8 LR rationales, priors** | ❌ **MISSING** | N/A |

### 4.2 Database
- `data/occris.db` — SQLite database present
- Schema includes: `vessels`, `ais_pings`, `spills`, `origin_zones`, `investigations`, `run_manifests`, `gateway_crossings`, `vessel_journeys`, `behaviour_events`, `audit_chain`

---

## 5. API Endpoints

### 5.1 Implemented Endpoints (`src/api/`)

**Main API** (`main.py`):
- ✅ `GET /api/dashboard/summary`
- ✅ `GET /api/cases`
- ✅ `GET /api/cases/{case_id}`
- ✅ `GET /api/cases/{case_id}/map`
- ✅ `GET /api/cases/{case_id}/spill`
- ✅ `GET /api/cases/{case_id}/origin-zone`
- ✅ `GET /api/cases/{case_id}/drift`
- ✅ `GET /api/cases/{case_id}/vessels`
- ✅ `GET /api/cases/{case_id}/vessels/{vessel_id}/track`
- ✅ `GET /api/cases/{case_id}/gateways`
- ✅ `GET /api/cases/{case_id}/gateway-events`
- ⚠️ `GET /api/cases/{case_id}/candidates` — **Returns hardcoded single vessel, not real M8 output**
- ❌ `POST /api/cases/{case_id}/report` — Stub only ("PDF Report triggered")

**Maritime API** (`maritime_router.py`):
- ✅ `GET /api/v1/maritime/evidence-bundle/{vessel_id}`
- ✅ `POST /api/v1/admin/rebuild`
- ✅ `GET /api/v1/admin/state`

**Verification API** (`verification.py`):
- ✅ `POST /api/v1/verification/run/{vessel_id}`
- ✅ `GET /api/v1/verification/report/{vessel_id}`
- ✅ `GET /api/v1/verification/case/{case_id}`
- ✅ `GET /api/v1/verification/ledger/verify`
- ✅ `POST /api/v1/verification/analyst-labels`
- ✅ `GET /api/v1/verification/review-queue`

**Missing M8 Endpoints**:
- ❌ `GET /api/v1/ranking/case/{case_id}`
- ❌ `GET /api/v1/ranking/vessels/{id}`
- ❌ `GET /api/v1/ranking/review-queue`
- ❌ `POST /api/v1/ranking/analyst-decision`

---

## 6. Critical Discrepancies vs. Prompt

### 6.1 Module 8 Status
**Prompt Claims**: "TODO (you build these): Module 8"  
**Reality**: Partial implementation exists in `src/investigation/` but:
- ❌ No odds-form Bayesian ranking engine
- ❌ No `evidence_engine.py` with LR breakdown
- ❌ No `sensitivity.py` (leave-one-out analysis)
- ❌ No `hypotheses.py` (H1-H5 schema)
- ❌ No `planner.py` (inspection planning)
- ❌ No `RankingBundleV1` frozen contract
- ❌ No `tools/bench/` OccurisBench framework
- ✅ Has `candidate_evidence.py`, `spatial_analysis.py`, `temporal_analysis.py`, `evidence_fusion.py` (foundation pieces)

**Assessment**: **30% complete** — evidence assembly exists, but core ranking logic is missing

### 6.2 Module 9 Status
**Prompt Claims**: "TODO (you build these): Module 9"  
**Reality**: React dashboard EXISTS and is functional:
- ✅ Design system implemented (dark theme, components)
- ✅ Live Map with MapLibre GL JS
- ✅ Vessel tracking, SAR layers
- ✅ Timeline & replay (basic)
- ✅ Spill analysis tab
- ✅ Candidate ranking tab (displays data)
- ❌ No WeasyPrint PDF export implementation
- ❌ No ledger verification UI
- ❌ No analyst decision buttons
- ❌ No Playwright E2E tests
- ❌ No "REPLAY | AIS Source: Synthetic" badge
- ❌ No "Investigation Priority ≠ Guilt" footer

**Assessment**: **70% complete** — core dashboard exists, missing forensic rigor features

### 6.3 Module 10 Status
**Prompt Claims**: "TODO (you build these): Module 10"  
**Reality**: **0% complete**
- ❌ No `scripts/run_demo.sh`
- ❌ No `docs/demo_narration.md`
- ❌ No offline demo pack with cached data
- ❌ No determinism double-run checks
- ❌ No failure drill tests

### 6.4 Missing Reference Documents
**Prompt Mentions**:
- `Occuris_Final_Solution_Overview.md` — ❌ **NOT FOUND**
- `Occuris_MVP_Implementation_Plan.md` — ❌ **NOT FOUND**
- `tools/fixtures/build_demo_scenarios.py` — ✅ EXISTS (at `tools/build_demo_scenarios.py`)
- `docs/bench/` — ❌ **DIRECTORY MISSING**

### 6.5 README vs. Reality
**Current README.md**:
- ✅ Has mission statement and core pitch
- ✅ Has architecture mermaid diagram (high-level, outdated)
- ❌ Does NOT document modules 0-10 individually with file maps
- ❌ Does NOT have frozen contracts section
- ❌ Does NOT have quickstart with offline demo
- ❌ Does NOT have data provenance section
- ❌ Does NOT have benchmarks section with OccurisBench results
- ❌ Does NOT have honest limitations section (per Overview §6-7)
- ❌ Does NOT have git workflow section
- **Verdict**: **README is aspirational marketing copy, not technical documentation matching code reality**

---

## 7. Stale Branches

```
remotes/origin/feature/module-5-maritime-memory  — MERGED (commit fcb4167)
remotes/origin/feature/module-6-ais-verification — MERGED (commit fc01ba6)
```

**Action Required**: Delete both stale remote branches after audit approved

---

## 8. Git Log Summary

Last 10 meaningful commits:
1. `e2f7a56` — Fix hardcoded API port (main HEAD)
2. `22df0c6` — Fix WindowResolution attribute error in M8
3. `8554f3b` — Implement Module 8 integration test (FAILING)
4. `94a0096` — Replace old frontend with React dashboard
5. `23e534f` — Implement Module 7 Counterfactual
6. `ff2b1de` — Merge Module 6
7. `fc01ba6` — Module 6 DoD report + tests
8. `f810a73` — Merge Module 5.1
9. `fcb4167` — Module 5.1 implementation
10. `ac670aa` — Module 4 SpillSplit v2

**Observations**:
- Clean linear history with feature branches
- Conventional commit messages mostly followed
- No direct pushes to main visible (good)

---

## 9. Action Items Summary

### Critical (Block Everything)
1. ❌ **Fix failing test** — `test_investigation_pipeline.py` expects non-existent `status` field
2. ❌ **Investigate coverage timeout** — likely infinite loop in test suite

### High Priority (M8 Blockers)
3. ❌ **Create `src/ranking/` module** with `evidence_engine.py`, `sensitivity.py`, `hypotheses.py`, `planner.py`
4. ❌ **Define `RankingBundleV1` frozen contract** in schemas
5. ❌ **Create `config/ranking.yaml`** with all LR rationales
6. ❌ **Build `tools/bench/` OccurisBench framework** with 300 scenarios
7. ❌ **Extend Merkle ledger** with `RANKING_ARTIFACT` event type

### Medium Priority (M9 Polish)
8. ❌ **Add WeasyPrint PDF export** in frontend
9. ❌ **Add honesty badges/footers** in UI
10. ❌ **Implement Playwright E2E tests**
11. ❌ **Add analyst decision buttons** to candidate dossier

### Medium Priority (M10 Setup)
12. ❌ **Create offline demo pack** for Cases A/B/C
13. ❌ **Write `scripts/run_demo.sh`** with determinism check
14. ❌ **Write `docs/demo_narration.md`** with caveats
15. ❌ **Implement failure drill tests**

### Low Priority (Cleanup)
16. ❌ **Delete stale remote branches** (module-5, module-6)
17. ❌ **Tag v1.0.0** after all DoD complete
18. ❌ **Fill README benchmark table** from bench report

---

## 10. Recommendation

**STATUS**: 🛑 **READY FOR README OVERHAUL, THEN M8 BUILD**

**Sequencing**:
1. **Fix failing test first** (5 min) — Remove `status` expectation or add field to contract
2. **README overhaul** per Section D (30 min) — Document AS-BUILT reality
3. **Build M8 from scratch** per Section E (4 hours) — Create ranking module
4. **Polish M9** per Section F (2 hours) — Add missing forensic features
5. **Build M10** per Section G (2 hours) — Offline demo + release
6. **Final integration** — Tests, determinism, v1.0.0 tag

**Estimated Total**: 8–10 hours of focused development

---

**Audit Complete** — Ready to proceed with README Task 1.
