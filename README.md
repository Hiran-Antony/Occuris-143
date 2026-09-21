# Occuris — Oil Spill Causal Attribution System

**Problem Statement 26143 — Smart India Hackathon 2026 (NTRO)**

Occuris is an intelligence-grade, forensically honest maritime causal attribution platform designed to track, explain, and attribute maritime events such as oil spills without premature accusation or bias.

---

## Module 5: Maritime Memory & Virtual Gateways Engine

Module 5 reconstructs and audits all vessel movements through monitored maritime corridors (e.g., the Arabian Sea economic zone). It provides objective answers to:
> *"Which vessels entered the monitored maritime region, where did they go, how long did they take, and was their movement normal or unexplained?"*

Module 5 operates with **zero guilt language**, never outputs accusations or culprit labels, and focuses strictly on empirical evidence, physical constraints, and verifiable provenance.

### Core Architecture

```mermaid
flowchart TD
    AIS[Raw AIS CSV / Live Stream] --> INGEST[AisSource / Ingestion Layer]
    INGEST --> TB[TrackBuilder & Gap Detector]
    CONFIG[(config/region.yaml)] --> GM[GatewayManager]
    TB --> CD[CrossingDetector - Exact Linear Interpolation]
    GM --> CD
    CD --> MM[MaritimeMemory - 5-State Journey Lifecycle]
    MM --> DA[DelayAnalyzer - 3-Tier Precedence]
    TB --> TRAFFIC[TrafficAnalyzer - Fixed Hourly Bins]
    WEATHER[(ERA5 Regional Wind NPZ)] --> BEHAVIOUR[BehaviourAuditor - Multi-Factor Synthesis]
    TRAFFIC --> BEHAVIOUR
    DA --> BEHAVIOUR
    
    subgraph Innovations [Four Innovation Layers]
        DNA[A. Behavioral DNA Extractor - Ledoit-Wolf Shrinkage]
        COLL[B. Collective Anomaly Detector - Multi-Vessel]
        DARK[C. Dark-Path Reconstructor - Physics Hypotheses]
        MERKLE[D. Merkle Audit Engine - Cryptographic Ledger]
    end
    
    TB --> DNA
    TB --> COLL
    TB --> DARK
    CD --> MERKLE
    
    BEHAVIOUR --> BUNDLE[EvidenceBundleV1 Contract]
    DNA --> BUNDLE
    COLL --> BUNDLE
    DARK --> BUNDLE
    MERKLE --> BUNDLE
```

---

### Key Capabilities & Innovation Layers

1. **Virtual Corridor Gateways & Exact Sub-Second Crossing**:
   - Monitored corridors defined strictly via `config/region.yaml`.
   - Exact linear time interpolation: $t_{cross} = t_1 + r(t_2 - t_1)$ with bounded $r \in [0.0, 1.0]$.
   - Idempotent suppression of duplicate pings and boundary noise.

2. **Maritime Memory (5-State Journey Tracking)**:
   - Tracks vessels through five mutually exclusive states: `COMPLETED`, `IN_REGION`, `ENTRY_ONLY_PARTIAL`, `EXIT_ONLY_PARTIAL`, and `WINDOW_INTERIOR`.

3. **Multi-Factor Delay Explanation**:
   - 3-tier expected duration precedence: (1) Historical profile ($\ge 5$ transits), (2) Corridor baseline speed (IMO commercial standard), (3) Insufficient history.
   - Objective explanations: Corridor traffic congestion ($\ge 75$th percentile), adverse ERA5 wind conditions, legitimate navigational status (at anchor, moored, restricted maneuverability).

4. **Innovation Layer A — Behavioral DNA Kinematic Signatures**:
   - Extracts 8 kinematic features (speed, acceleration, turn-rate moments, loiter ratio, path straightness).
   - Computes symmetric regularized Mahalanobis re-identification distances across blackout boundaries using Ledoit-Wolf covariance shrinkage.

5. **Innovation Layer B — Collective Fleet Anomaly Detection**:
   - Rule R1: Coordinated dark vessels (temporal overlap & spatial proximity).
   - Rule R2: Rendezvous at sea (proximity $< 500\text{ m}$ for $\ge 20\text{ min}$ at low speed).
   - Rule R3: Trajectory convergence & parallel steaming.

6. **Innovation Layer C — Physics-Informed Dark-Path Reconstruction**:
   - Reconstructs unobserved trajectories during AIS coverage gaps across 4 physical hypotheses: Geodesic, Rhumb line, DNA-prior, and CMEMS Ocean Current-assisted advection.
   - Evaluates kinematic feasibility against maximum vessel capabilities and computes normalized softmax cost probabilities.

7. **Innovation Layer D — Tamper-Evident Merkle Audit Ledger**:
   - Hash-chains all crossing events from genesis (`0`*64) forward.
   - Periodically anchors Merkle roots and SHA-256 dataset provenance hashes (`input_csv_hash`, `region_yaml_hash`, `pipeline_params_hash`) into SQLite `run_manifests`.
   - Instantly detects any historical database tampering or out-of-order mutations.

---

### Verification & Testing

Module 5 includes 58 automated tests across unit, integration, property, contract, and architectural integrity suites.

```bash
# Run complete test suite with coverage report
pytest tests/ --cov=src/ais --cov-fail-under=85

# Run individual verification suites
pytest tests/contract/ -v      # Frozen EvidenceBundleV1 schema verification
pytest tests/property/ -v      # Mathematical and invariance properties
pytest tests/integrity/ -v     # Zero-guilt language & import boundaries
pytest tests/integration/ -v   # Full pipeline integration with ground truth
```

### Forensic Evidence Bundle API

```http
GET /api/v1/maritime/evidence-bundle/{vessel_id}?case_id=CASE-2026-001
```

Exports the frozen `EvidenceBundleV1` structure consumed by downstream analytical modules:
- Complete vessel journey milestones
- Detected AIS coverage blackouts
- Empirically grounded delay analysis
- Objective multi-factor behavioral assessment
- Kinematic Behavioral DNA match scores
- Multi-vessel collective anomaly associations
- Physics-informed candidate dark paths
- Cryptographic Merkle provenance root and row hashes