# Changelog

All notable changes to the Occuris project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- **Module 10 Descoped**: Removed Module 10 (Offline Demo & Integration) from project scope by owner decision
  - Removed Module 10 section from README documentation
  - Removed M10 node from architecture mermaid diagram
  - Preserved Module 10's cross-cutting guarantees as system-wide requirements:
    - Deterministic offline execution (same inputs + seed ⇒ identical hashes)
    - No-egress guarantee for tests (zero network calls)
    - Honest demo caveats (probability zone ≠ pin, priority ≠ guilt, REPLAY badge)
  - Added new "Demo & Honesty" section to README documenting cross-cutting guarantees
  - Updated all module references from "M0-M10" to "M0-M9"

### Added
- **Kiro Onboarding Audit Report** (`docs/kiro_onboarding_audit.md`): Comprehensive repository exploration with module inventory, contract verification, test status, and discrepancy analysis
- **Kiro Completion Audit Report** (`docs/kiro_completion_audit.md`): Phase 0 verification for final release preparation with critical issue identification

### Changed (Previous)
- **README Overhaul**: Complete rewrite to match as-built code reality
  - Added detailed module-by-module documentation (M0-M10) with file maps, algorithms, inputs/outputs, API endpoints, config keys, tests, and DoD status
  - Added architecture mermaid diagram covering full pipeline with frozen contracts
  - Added frozen contracts reference section (EvidenceBundleV1, Module6VerificationBundleV1, RankingBundleV1 planned)
  - Added quickstart guide with installation, configuration, and run instructions
  - Added data provenance & honesty badges section (SYNTHETIC_REPLAY vs LIVE_FEED)
  - Added benchmarks section placeholder for OccurisBench (Top-1, Top-3, IVFF, ECE)
  - Added honest limitations section with mandatory disclaimers
  - Added complete repository tree diagram
  - Added git workflow documentation (feature branches, PR process, release tagging)
  - Marked incomplete modules with status warnings (M8 30%, M9 70%, M10 0%)
  - Removed aspirational marketing language, replaced with technical documentation

### Fixed
- **Module 8 Evidence Fusion**: Fixed `AttributeError` in `evidence_fusion.py` where `m6.status` was accessed instead of `m6.ais_state` (Module6VerificationBundleV1 frozen contract field)

---

## [6.0.0] - 2026-09-22

### Added
- **Six-Stage AIS Verification Engine (`src/verification/`)**:
  - `Stage 1: WindowResolver`: Resolves intersection between vessel presence and investigation spill release window with configurable padding.
  - `Stage 2: ContinuityAnalyzer`: Audits AIS gaps, calculates spatial/temporal gap concurrency index against all other vessels in the vicinity, and flags regional infrastructure coverage outages.
  - `Stage 3: KinematicEngine`: Constant-Velocity Extended Kalman Filter (CV-EKF in local ENU coordinates) with $\chi^2(2)$ NIS test, episode grouping, and simultaneous identity conflict detection (>50 km within 30 min).
  - `Stage 4: ReachabilityEngine`: Validates physical reachability of consecutive reported pings and unobserved candidate round-trips to probable spill origin zones, assisted by CMEMS ocean currents.
  - `Stage 5: DarkPathValidator`: Validates kinematic feasibility and origin-zone intersection for unobserved blackout intervals, preserving the mandatory hypothesis disclaimer.
  - `Stage 6: StateClassifier`: Multi-hypothesis evidential softmax competition (`{COVERAGE, WEATHER, TRAFFIC, OPERATIONAL, CONCEALMENT_PATTERN}`), Bayesian odds-form posterior track integrity ($P(\text{reliable} \mid \text{evidence})$) with sensitivity intervals, and forensic decision rules (`NORMAL`, `AIS_GAP_DARK`, `REPORTING_ANOMALY`, `AMBIGUOUS`).
- **Frozen Contracts (`src/ais/schemas.py`)**:
  - `Module6VerificationBundleV1` downstream verification contract.
  - `WindowResolution`, `ContinuityReport`, `KinematicReport`, `ReachabilityResult`, `DarkPathValidation`, `AnomalyState`, `AnalystLabel`.
  - Enums: `VerificationStageStatus`, `AnomalyClassification`, `KinematicFlag`, `AisState`, `ReachabilityVerdict`.
- **Single Merkle Audit Extension**: Extended Module 5 Merkle chain with `VERIFICATION_ARTIFACT` records and full ledger verification.
- **Verification API (`/api/v1/verification/`)**:
  - `POST /run/{vessel_id}`: Idempotent full 6-stage verification run returning bundle and ledger hash.
  - `GET /report/{vessel_id}`: Cached report retrieval with provenance input hashes.
  - `GET /case/{case_id}`: All vessel reports for an investigation case.
  - `GET /ledger/verify`: Comprehensive audit ledger verification covering Module 6 records.
  - `POST /analyst-labels`: Human analyst label persistence (storage-only, no ML feedback loop).
  - `GET /review-queue`: Verification review queue sorted by integrity interval width (most ambiguous first).
- **Configuration**:
  - Created `config/verification.yaml` as single source of truth for all EKF, Bayesian integrity, reachability, concurrency, and explanation weights with documented LR rationales. Zero magic numbers.
- **Automated Testing Suite**: 120 passing tests achieving 92% statement coverage across `src/verification/`.

---

## [5.1.0] - 2026-09-21

### Added
- **Frozen Contract**: `EvidenceBundleV1` schema in `src/ais/schemas.py` providing deterministic, structured exports of maritime memory, kinematic delays, behavioral DNA, collective anomalies, dark paths, and Merkle audit roots.
- **API Endpoints**:
  - `GET /api/v1/maritime/evidence-bundle/{vessel_id}`: Exports frozen EvidenceBundleV1 for a vessel and case.
  - `POST /api/v1/admin/rebuild`: DEV-guarded full pipeline rebuild endpoint.
  - `GET /api/v1/admin/state`: Diagnostic endpoint returning current build ID, input hash, config hash, seed, and build timestamps.
- **Determinism & Provenance**: `run_manifests` SQLite tracking table and SHA-256 provenance hashing of input CSV, `config/region.yaml`, and pipeline parameter sets.
- **Testing Suite**: 58 automated tests across `unit`, `integration`, `property`, `contract`, and `integrity` suites achieving 93% statement coverage across `src/ais/`.
- **Property-Based Invariants**:
  - Geodesic crossing linear interpolation ratio boundedness ($r \in [0.0, 1.0]$).
  - Mahalanobis distance symmetry ($D(A,B) = D(B,A)$) and non-negativity.
  - Softmax candidate dark path probability normalization ($\sum p_i = 1.0$).
  - Build determinism given identical random seed and input files.
- **Architectural Guards**:
  - Automated regex guard enforcing zero guilt/accusatory language across all AIS modules.
  - Import guard preventing forbidden drift modeling or attribution scoring imports in Module 5.

### Changed
- **Configuration Externalization**:
  - Migrated `merkle_window_events`, `weather_wind_ms`, `vessel_max_speed_kn`, and `traffic_bin_minutes` into `config/region.yaml`.
  - Zero magic numbers remain hardcoded in `src/ais/`.
- **Behavioral DNA Covariance**:
  - Implemented Ledoit-Wolf shrinkage estimator for sample covariance calculation with diagonal regularized fallback.
  - Symmetrized profile comparisons using pooled covariance matrices.
- **Maritime Memory Journey Lifecycle**:
  - Expanded `JourneyStatus` to 5 distinct states: `COMPLETED`, `IN_REGION`, `ENTRY_ONLY_PARTIAL`, `EXIT_ONLY_PARTIAL`, and `WINDOW_INTERIOR`.
- **Delay Analysis**:
  - Enforced strict 3-tier precedence: (1) Historical (>= 5 journeys), (2) Corridor Baseline (per-class speed), (3) Insufficient History.
- **Cryptographic Merkle Audit Engine**:
  - Anchored SHA-256 provenance hashes directly into `AuditAnchor` records.
  - Supported flexible event ingestion and verification over active and archived crossing ledgers.
