# Phase 2 Engineering Specification: Adaptive Dynamic Virtual Gateways

## 1. Executive Summary
In the MVP implementation of Module 5 (Maritime Memory & Virtual Gateways), virtual corridors (`GATE_A`, `GATE_B`, `GATE_C`, `GATE_D`) are statically defined in `config/region.yaml` as narrow polygons positioned across established maritime choke-points and traffic routes.

In real-world operations, seasonal monsoon shifts (e.g. Southwest vs. Northeast monsoon in the Arabian Sea), weather-routed diversions, and maritime security zones shift principal vessel flows by 10–50 nautical miles over monthly horizons. This design specification documents the architecture for Phase 2 **Adaptive Dynamic Gateways**, which autonomously optimize corridor positions without breaking historical audit continuity.

---

## 2. Mathematical Foundation: Kernel Density Corridors

### 2.1 Empirical Flow Estimation
Rather than manual geofencing, Adaptive Gateways continuously fit an anisotropic 2D Gaussian Kernel Density Estimator (KDE) over historical AIS trajectories:

$$\hat{f}(x, y) = \frac{1}{n h_x h_y} \sum_{i=1}^{n} K\left(\frac{x - x_i}{h_x}, \frac{y - y_i}{h_y}\right)$$

where $(x_i, y_i)$ are observed ping coordinates and $h_x, h_y$ are bandwidth parameters aligned with the principal eigenvectors of local vessel velocity tensors.

### 2.2 Transverse Ridge Extraction
1. **Streamline Tracking**: Major commercial routes correspond to local maxima ridges in the KDE density surface $\nabla \hat{f}(x, y) \cdot \mathbf{v}_\perp = 0$.
2. **Orthogonal Gate Placement**: A dynamic gateway corridor $G_k$ is placed orthogonal to the dominant flow vector $\bar{\mathbf{v}}$:
   $$\mathbf{n}_{gate} = \frac{\bar{\mathbf{v}}}{\|\bar{\mathbf{v}}\|}, \quad \text{Line} = \mathbf{x}_c + \lambda \mathbf{n}_{gate}^\perp$$
   with corridor width bounded by the $2.5\sigma$ lateral dispersion.

---

## 3. Architecture & Data Foundation
Module 5 already exposes the data foundation needed for this adaptation:
- `GET /api/v1/maritime/traffic-density` returns discrete temporal bins with `percentile_class` (`HIGH`, `NORMAL`, `LOW`) derived from empirical AIS counts.
- `GET /api/v1/gateways` exposes GeoJSON polygon geometries with immutable identifiers.

### Adaptation Pipeline
```
[Historical AIS Pings] ──> [TrafficAnalyzer] ──> [KDE Flow Extractor]
                                                       │
                                                       ▼
[Audit Anchors] <── [Merkle Revision Event] <── [Corridor Optimization]
```

---

## 4. Cryptographic & Forensic Continuity (Guarding the Merkle Ledger)
A critical requirement for forensic integrity (SIH Problem Statement 26143, NTRO) is that **gateway repositioning must never invalidate past crossing events or transit analyses**:

1. **Gateway Versioning**: Each gateway has a monotonic revision integer (e.g. `GATE_A_v1`, `GATE_A_v2`).
2. **Temporal Validity Windows**: Gateways define `valid_from` and `valid_until` UTC timestamps.
3. **Audit Chaining**: When a gateway corridor is re-optimized, a `GATEWAY_RECONFIG_EVENT` is appended to the tamper-evident Merkle hash chain in `gateway_events`, locking the old boundary geometry in historical Merkle roots before the new corridor activates.

---

## 5. Implementation Roadmap
| Milestone | Description | Target |
|---|---|---|
| **Phase 2.1** | Background worker computing 30-day KDE flow ridges | Q3 2026 |
| **Phase 2.2** | Automated candidate gateway recommendation API | Q4 2026 |
| **Phase 2.3** | Human-in-the-loop operator approval UI for corridor updates | Q1 2027 |
