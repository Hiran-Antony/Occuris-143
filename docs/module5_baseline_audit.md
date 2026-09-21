# Module 5 — Baseline Audit Report (Phase 0)

**Date:** 2026-09-21  
**Auditor:** Module 5.1 Hardening Pass  
**Scope:** `src/ais/`, `src/api/maritime.py`, `config/region.yaml`, `src/config.py`, `tests/`

---

## A1 — `merkle_window_events` Inconsistency

**Verdict: CONFIRMED**

| Location | Value | Source |
|----------|-------|--------|
| `config/region.yaml:77` | `merkle_window_events: 100` | YAML config |
| `src/ais/audit.py:73` | `def __init__(self, checkpoint_window_events: int = 100)` | Default parameter |
| `src/api/maritime.py:75` | `MerkleAuditEngine(checkpoint_window_events=50)` | **HARDCODED 50** |
| `src/api/maritime.py:144` | `MerkleAuditEngine(checkpoint_window_events=50)` | **HARDCODED 50 (duplicate)** |

**Impact:** The config file declares 100 but the API engine overrides with 50 in two places. Neither place reads from config. This means anchors are created at a different cadence than documented.

---

## A2 — `traffic.py` Sliding-Window vs Fixed-Hour-Bin Ambiguity

**Verdict: CONFIRMED**

**Evidence:**

1. `traffic.py:34` docstring says *"rolling traffic density bins"* but default `step_minutes=60` equals `bin_duration_minutes=60`, making them **fixed non-overlapping bins**.

2. `traffic.py:104` — `get_traffic_at_time()` uses a **completely different** threshold:
   ```python
   is_high = count >= 3  # HARDCODED magic number
   ```
   This ignores the configured `percentile_threshold=75.0` entirely. The `compute_density_bins()` method (line 64) correctly uses `np.percentile(counts, self.percentile_threshold)`, but `get_traffic_at_time()` does not — it uses a hardcoded `>= 3`.

3. The `get_traffic_at_time()` result is what actually feeds into `BehaviourAuditor` via `maritime.py:111-117`, meaning **the real behaviour pipeline uses the hardcoded threshold, not the percentile-based one**.

**Impact:** Traffic-based delay explanations are driven by a magic number, not the configured percentile. The documented percentile logic in `compute_density_bins` is only used for the `/traffic-density` API response, not for behaviour assessment.

---

## A3 — Hardcoded 6.5 m/s Wind Threshold & 18 kn Max Speed

**Verdict: CONFIRMED**

| Location | Hardcoded Value | Should Come From |
|----------|----------------|-----------------|
| `src/ais/behaviour.py:170` | `wind_spd >= 6.5` | `config/region.yaml` (missing key) |
| `src/ais/dark_path.py:71` | `max_vessel_speed_knots: float = 18.0` | `config/region.yaml` (missing key) |
| `src/config.py:88` | `MAX_VESSEL_SPEED_KN = 18.0` | Legacy, not used by Module 5 AIS code |

`config/region.yaml` currently has **no** `weather_wind_ms` or `vessel_max_speed_kn` keys. Both values are buried as inline literals.

---

## A4 — `dna.py` Mahalanobis Covariance Singularity Risk

**Verdict: CONFIRMED**

**Evidence:**

1. `dna.py:133-142` — The "covariance" is a hardcoded diagonal array of constants:
   ```python
   variances = np.array([
       max(0.5, (dna_a.feature_vector.get("speed_std", 1.0) ** 2)),
       0.5, 0.01, 0.01, 0.05, 0.05, 0.04, 0.02,
   ])
   ```
   This is not a sample covariance — it's a hand-picked diagonal. The first element uses one feature from `dna_a`, making the distance **asymmetric** (`compare_dna(A, B) ≠ compare_dna(B, A)`).

2. `schemas.py:309` — `covariance: Optional[List[List[float]]] = None` is declared but **never populated** (`dna.py:112-118` always passes `covariance=None`).

3. No Ledoit-Wolf shrinkage, no ridge regularization, no sample covariance estimation at any point.

4. `DnaMatch` schema (`schemas.py:316-322`) has `method: str = "MAHALANOBIS_DNA_RE_ID"` but doesn't distinguish between full-covariance vs diagonal vs shrunk approaches.

**Impact:** Re-identification confidence percentages are not grounded in learned distributions. With < 3 pings, the feature vector is all zeros (line 43), making Mahalanobis distance meaningless. The asymmetry bug means `compare_dna(A, B) ≠ compare_dna(B, A)`.

---

## A5 — `delay_analysis` Historical Tier Unreachable

**Verdict: CONFIRMED**

**Evidence:**

1. `delay_analysis.py:62` — Historical tier requires `len(historical_durations) >= self.min_history_count` (5 by default).

2. `src/api/maritime.py:107` — The API calls:
   ```python
   self.transits = self.delay_analyzer.analyze_all(self.journeys)
   ```
   with **no** `history_map` argument (it defaults to `{}`).

3. `delay_analysis.py:116` — `hist_map = history_map or {}` → always empty → always falls through to Tier 2 (CORRIDOR_BASELINE) or Tier 3.

4. The demo dataset generates **one** journey per vessel, so even if history_map were passed, `min_history_count=5` would never be satisfied.

**The fallback IS explicit** (returns `ExpectedTimeBasis.CORRIDOR_BASELINE` with `z_score=None`), satisfying the "never silently substitute" principle. But the HISTORICAL tier is effectively dead code in the current system.

---

## A6 — Journey Status Enum Semantics Ambiguous

**Verdict: CONFIRMED**

**Current enum** (`schemas.py:35-39`):
```python
class JourneyStatus(str, Enum):
    COMPLETED = "COMPLETED"
    IN_REGION = "IN_REGION"
    PARTIAL_ENTRY_ONLY = "PARTIAL_ENTRY_ONLY"
    PARTIAL_EXIT_ONLY = "PARTIAL_EXIT_ONLY"
```

**Assignment logic** (`maritime_memory.py:84-108`):
| Condition | Status Assigned | Semantic Meaning |
|-----------|----------------|-----------------|
| Entry + Exit crossings | `COMPLETED` | Clear |
| Entry only, no exit | `PARTIAL_ENTRY_ONLY` | Entered, still inside |
| No entry, exit only | `PARTIAL_EXIT_ONLY` | Was inside at data start |
| No crossings at all | `IN_REGION` | **Ambiguous** |

**Ambiguity:** `IN_REGION` conflates two cases:
- Vessel pings are entirely inside the monitored zone (never crossed a boundary)
- Vessel pings don't intersect any gateway (could be outside, near boundaries, or partial data)

Missing state from spec: `WINDOW_INTERIOR` — for vessels whose entire observation window is within the region with no boundary crossing.

---

## A7 — `MaritimeEngineState` Singleton Has No Invalidation/Rebuild Path

**Verdict: CONFIRMED**

**Evidence:**

1. `src/api/maritime.py:211` — Module-level singleton:
   ```python
   engine = MaritimeEngineState()
   ```

2. `src/api/maritime.py:214-219` — One-shot initialization:
   ```python
   def ensure_pipeline():
       if not engine.initialized:
           ...
           engine.load_and_process(csv_to_load)
   ```

3. No `rebuild()`, `invalidate()`, `reset()`, or `POST` endpoint exists anywhere in the file.

4. If `region.yaml` is modified or new AIS data arrives, the only way to refresh is to **restart the entire uvicorn process**.

**Impact:** Stale cache; development/testing friction; no way to trigger a rebuild via API for integration tests.

---

## A8 — Tests, Ground-Truth Fixtures, DoD Report

**Verdict: PARTIAL**

| Item | Status | Location |
|------|--------|----------|
| Test file | EXISTS | `tests/test_module5.py` (314 lines, 10 test methods) |
| Structured `tests/unit/` hierarchy | ABSENT | Flat single file |
| Property-based tests | ABSENT | No `hypothesis` tests |
| Contract tests (schema snapshot) | ABSENT | No JSON schema validation |
| Integrity tests (no ground_truth in src/) | ABSENT | No grep guards |
| Coverage measurement | ABSENT | No `pytest-cov` configuration |
| `tools/build_demo_scenarios.py` | EXISTS | 7,808 bytes |
| `data/raw/synthetic/ground_truth.json` | **UNKNOWN** (may exist on disk) | Referenced but not verified on this machine |
| DoD report | ABSENT | Not in `docs/` |
| `docs/` contents | Only `phase2_adaptive_gateways.md` | No DoD, no README section |

---

## A9 — Audit Anchors Lack Config/Input Hashes

**Verdict: CONFIRMED**

**Current `AuditAnchor` schema** (`schemas.py:367-375`):
```python
class AuditAnchor(BaseModel):
    anchor_id: str
    merkle_root: str
    event_count: int
    window_start: datetime
    window_end: datetime
    external_tx_id: Optional[str] = None
    created_at: str
```

**Missing fields:**
- `input_csv_hash` — SHA-256 of the source AIS CSV
- `region_yaml_hash` — SHA-256 of the configuration file
- `pipeline_params_hash` — Hash of runtime parameters (seed, thresholds)

Without these, two different input datasets could produce anchors that appear identical in structure but represent entirely different evidence chains. Reproducibility auditing requires knowing *what data produced this chain*.

---

## Summary Table

| ID | Issue | Verdict | Severity |
|----|-------|---------|----------|
| A1 | Merkle window 100 vs 50 | **CONFIRMED** | Medium — anchor cadence mismatch |
| A2 | Traffic sliding vs fixed + hardcoded ≥3 | **CONFIRMED** | High — behaviour assessment uses magic number |
| A3 | Hardcoded wind 6.5 m/s + max speed 18 kn | **CONFIRMED** | Medium — not config-driven |
| A4 | DNA diagonal variances, no regularization, asymmetry | **CONFIRMED** | High — asymmetric distance + no learned covariance |
| A5 | Historical delay tier dead code | **CONFIRMED** | Low — fallback is explicit |
| A6 | Journey status enum ambiguity | **CONFIRMED** | Medium — IN_REGION overloaded |
| A7 | Engine singleton no rebuild path | **CONFIRMED** | Medium — stale-cache, no dev rebuild |
| A8 | Test structure incomplete | **PARTIAL** | High — no property/contract/integrity tests |
| A9 | Audit anchors lack provenance hashes | **CONFIRMED** | Medium — reproducibility gap |

**All 9 items: 8 CONFIRMED + 1 PARTIAL. Zero REFUTED.**

Phase 0 complete. Ready to proceed to Phase 1.
