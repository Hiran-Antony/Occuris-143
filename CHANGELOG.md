# Changelog

All notable changes to the Occuris project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
