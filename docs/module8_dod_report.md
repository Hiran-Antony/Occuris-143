# Module 8 — Definition of Done Report

> **Status**: ✅ COMPLETE
> **Date**: 2026-09-24
> **Branch**: `feature/module-8-rebuild`

---

## Checklist

### Critical (Blocking)

- [x] **Fix hardcoded candidates endpoint** — Replaced canned V004 response with real dynamic pipeline results
- [x] **Fix test timeout** — `test_investigation_pipeline.py` passes in <2s (was timing out)
- [x] **Create `config/ranking.yaml`** — 458 lines, all priors/LRs/discounts documented, zero magic numbers
- [x] **Define RankingBundleV1 contract** — Frozen schema in `src/ais/schemas.py` with 6 priority states

### Module 8 Core

- [x] **Evidence Engine** (`src/ranking/evidence_engine.py`) — Odds-form Bayesian posterior, dependency discounting (max-LR within groups, geometric mean across groups), factor extraction from M5/M6/M7
- [x] **Sensitivity Analysis** (`src/ranking/sensitivity.py`) — Leave-one-out analysis, influence classification (HIGH/MEDIUM/LOW), posterior uncertainty intervals
- [x] **Multi-Source Hypotheses** (`src/ranking/hypotheses.py`) — H1 single-source, H2 two-source coordinated via SpillSplit reuse with BIC penalties and softmax; H3-H5 return INSUFFICIENT_DATA
- [x] **Inspection Planner** (`src/ranking/planner.py`) — Greedy submodular optimization under patrol endurance budget with Haversine distance
- [x] **Priority Classifier** (`src/ranking/classifier.py`) — All 6 states: HIGH, MEDIUM, LOW, AMBIGUOUS, NO_STRONG_MATCH, INSUFFICIENT_DATA
- [x] **Ranking Pipeline Orchestrator** (`src/ranking/ranking_pipeline.py`) — Full M5+M6+M7+SpillSplit orchestration producing RankingBundleV1
- [x] **API Endpoints** (`src/ranking/api.py`) — 5 routes: case ranking, vessel detail, review queue, analyst decision, legacy candidates
- [x] **Merkle Audit Extension** (`src/ranking/audit.py`) — RANKING_ARTIFACT events, SQLite persistence, tamper verification

### OccurisBench

- [x] **Scenario Generator** (`tools/bench/generate_attribution_scenarios.py`) — 5 classes, 300 seed-controlled scenarios
- [x] **Calibration** (`tools/bench/calibration.py`) — Platt scaling, ECE computation
- [x] **Benchmark Runner** (`tools/bench/run_bench.py`) — Full pipeline evaluation with calib/eval split isolation
- [x] **Report Generator** (`tools/bench/report.py`) — Markdown report to `docs/bench/attribution_bench_report.md`

### Metrics (300 scenarios, seed=42)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Top-1 Accuracy** | 1.0000 | ≥ 0.80 | ✅ PASS |
| **Top-3 Coverage** | 1.0000 | ≥ 0.90 | ✅ PASS |
| **IVFF** | 0.0000 | ≤ 0.10 | ✅ PASS |
| **ECE** | 0.0142 | ≤ 0.10 | ✅ PASS |

Runtime: 25.0s (target: <3 min)

### Tests

| Suite | Tests | Status |
|-------|-------|--------|
| `tests/integrity/test_guards.py` | 4 | ✅ All pass |
| `tests/unit/test_ranking_sensitivity.py` | 2 | ✅ All pass |
| `tests/unit/test_ranking_hypotheses.py` | 3 | ✅ All pass |
| `tests/unit/test_ranking_planner.py` | 2 | ✅ All pass |
| `tests/unit/test_ranking_classifier.py` | 1 | ✅ All pass |
| `tests/integration/test_ranking_api.py` | 6 | ✅ All pass |
| `tests/integration/test_ranking_pipeline.py` | 14 | ✅ All pass |
| **Total** | **32** | ✅ **All pass in 2.75s** |

### Compliance

- [x] Zero magic numbers — all parameters from `config/ranking.yaml`
- [x] Ground truth isolation — `src/ranking/` never references `ground_truth.json` or `tools/bench/`
- [x] Calibration isolation — Platt scaling fitted strictly on calib split (90 scenarios), never on eval split
- [x] No guilt language — "Investigation Priority ≠ Guilt" enforced in schemas, API, and PDF disclaimer
- [x] UTC ISO-8601 timestamps throughout
- [x] Frozen contracts — `RankingBundleV1` in `src/ais/schemas.py`
- [x] Merkle ledger integrity — RANKING_ARTIFACT events extend existing chain

---

*Generated as part of SIH 2026, PS 26143 (NTRO) — Occuris Module 8 completion.*
