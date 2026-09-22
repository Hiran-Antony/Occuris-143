# Occuris — AI-Powered Causal Attribution System for Oil Spill Forensics

**SMART INDIA HACKATHON 2026**
* **Team Name:** Team Surf Excel (Team ID: K26108)
* **Problem Statement ID:** 26143
* **Problem Statement Title:** Leveraging satellite imagery to determine Oil spills at sea along with AIS data correlations to identify vessel responsible for the spill.
* **Theme:** Disaster Management
* **Category:** Software

---

## 🚨 The Problem

1. **Oil spills are difficult to trace:** Wind and ocean currents move the oil, making its original location, release time, and movement difficult to determine.
2. **Identifying the source vessel is difficult:** Heavy traffic, missing AIS signals (spoofed or dark vessels), and unusual vessel movements make it difficult to filter and prioritize relevant vessels.

## 💡 Our Solution: Occuris

Occuris reconstructs how an oil spill moved, traces it to probable source zones, and verifies which vessels could physically explain the spill. 

### Uniqueness & Innovation

* **SpillSplit:** Separates a single spill into possible multiple source hypotheses instead of attributing the entire spill to one vessel automatically.
* **Counterfactual Trajectory Reasoning:** Simulates oil released from each candidate vessel to check whether its movement can physically explain the observed spill.
* **Tri-Layer AIS Verification:** Checks normal AIS, transmission gaps, and physically impossible routes before ranking vessels for investigation.

---

## ⚙️ System Architecture

```mermaid
flowchart TD
    %% Multi-Source Data Ingestion
    SAR[Sentinel-1 SAR] --> DVN[Data Validation & Normalization]
    AIS[AIS Data] --> DVN
    WIND[Wind/Ocean Currents] --> DVN

    DVN --> |Branch 1| MMON[Maritime Monitoring]
    DVN --> |Branch 2| OSF[Oil Spill Forensics]

    %% Maritime Monitoring Branch
    subgraph Maritime Monitoring
        GWA[Gateway A] --> VJT[VESSEL JOURNEY TRACKING]
        GWB[Gateway B] --> VJT
        GWC[Gateway C] --> VJT
        VJT --> MMEM[Maritime Memory]
        GWD[Gateway D] --> BA[Behaviour Analysis]
        BA --> EAA[Expected vs Actual Behaviour]
    end

    %% Oil Spill Forensics Branch
    subgraph Oil Spill Forensics
        SSD[SAR Spill Detection] --> LAV[Look-Alike Verification]
        LAV --> SC[Spill Characterization]
        FDF[Future Drift Forecast] --> ORR[Origin & Release Reconstruction]
        ORR --> SSA[Spill-Split Analysis]
        SSA --> OUT[Outputs: One vessel / Two vessel]
    end

    %% Context-Aware Analysis
    subgraph Context-Aware Analysis
        WEATHER[Weather]
        TRAF[Traffic]
        AISA[AIS Anomalies]
        OPS[Operational Stops]
    end
    MMEM -.-> Context-Aware Analysis

    %% Memory Rewind & Investigation
    OUT --> MRE[MEMORY REWIND ENGINE]
    Context-Aware Analysis --> MRE
    MRE --> |Origin + Time, Search History| FC[Filter Candidates]
    FC --> IPRI[INVESTIGATION PRIORITY: High, Medium, Low]
    
    IPRI --> TLAIS[TRI-LAYER AIS VERIFICATION: Time + Route + Behaviour]
    
    subgraph Tri-Layer AIS Verification
        NAIS[Normal AIS]
        DARK[AIS Gap / Dark]
        SPOOF[Spoofed]
    end
    TLAIS --> NAIS & DARK & SPOOF

    %% Counterfactual Trajectory Reasoning
    NAIS & DARK & SPOOF --> CTR[Counterfactual Trajectory Reasoning]
    
    subgraph Counterfactual Simulation
        ST[SHIP TRACK] --> DSIM[DRIFT SIMULATION]
        DSIM --> SSP[SIMULATED SPILL PATH]
        SSP --> PSM[PHYSICAL SPILL MATCH]
    end
    CTR --> Counterfactual Simulation

    %% Dashboard Output
    PSM --> DB[OCCURIS DASHBOARD]
    
    subgraph Dashboard Features
        LM[Live Map]
        VT[Vessel Timeline]
        SA[Spill Analysis]
        CR[Candidate Ranking]
        CREP[Case Report]
    end
    DB --> LM & VT & SA & CR & CREP
```

---

## 🛠️ Technology Stack

**DATA:** 
* **Sentinel-1 SAR**, **MarineCadastre AIS**, **CMEMS / INCOIS**, **SQLite → PostgreSQL**
* *Unifies satellite imagery, vessel history, and ocean conditions.*

**COMPUTE:**
* **Python**, **FastAPI**, **Pydantic**, **Pandas**, **GeoPandas**
* *Processes and validates maritime & geospatial data.*

**AI & FORENSICS:**
* **PyTorch**, **SegFormer-B0** (SAR Detection)
* **RK4 Drift** (Hydrodynamic modeling)
* **EM-GMM** (SpillSplit clustering)
* **EKF**, **Maritime Memory Gateway Engine**
* *Detects spills, reconstructs drift, and evaluates vessel behaviour with AIS Behaviour Auditing and Vessel Spill Simulation.*

**INTERFACE:**
* **React**, **TypeScript**, **MapLibre GL JS**, **Recharts**, **WeasyPrint**
* *Transforms analysis into maps, timelines, rankings, and reports.*

---

## 📊 Feasibility and Viability

| Aspect | Technical | Analysis of the Feasibility of the Idea | Potential Challenges & Risks | Strategies for Overcoming These Challenges |
| :--- | :--- | :--- | :--- | :--- |
| **Multiple-Source Spill** | SpillSplit + EM-GMM | Separates one observed slick into 1-source or 2-source hypotheses using backtracked origins. | A single slick can merge after drifting, making separate sources difficult to distinguish. | Cluster + drift consistency (EM-GMM groups probable origins; drift consistency checks whether each cluster can explain the observed slick.) |
| **Counterfactual Trajectory Reasoning** | AIS + RK4 Drift Simulation | Tests a hypothetical release from each candidate vessel against the observed SAR spill. | A nearby vessel may not physically explain the spill. | Multi-factor physical matching (simulate forward with RK4; compare location, shape, direction, spread, and timing.) |
| **AIS Uncertainty** | Tri-Layer AIS Verification | Reconstructs vessel history even when AIS records are incomplete or inconsistent. | AIS gaps and anomalies can create misleading vessel associations. | Cross-layer verification (classify Normal, AIS Gap and Spoofed / Reporting Anomaly; cross-check each against physical spill evidence.) |

---

## 🌍 Impact and Benefits

### Direct Impact on Target Users
* **Actionable Coast Guard Intelligence:** Empowers the Indian Coast Guard by turning manual suspect tracking along India’s 7,500+ km coastline into an automated, proactive pipeline.
* **Court-Ready Evidence:** Eliminates investigative guesswork by instantly filtering thousands of regional ships down to the top 1–3 highly probable suspects using mathematically explainable dossiers.

### Strategic Scale of Impact
* **EEZ & Trade Security:** Continuously monitors virtual maritime corridors across India’s 2.01 million sq. km Exclusive Economic Zone (EEZ), safeguarding the waters where 95% of national trade volume operates.
* **Protecting Coastal Livelihoods:** Directly safeguards the economies of approximately 4 million Indian marine fisherfolk by predicting 24–72 hour oil drift, allowing preemptive containment before the oil impacts vulnerable shores.

### Sustainability & Deployment Model
| Stage | User / Payer | What they receive | Sustainability model |
| :--- | :--- | :--- | :--- |
| **Pilot** | Indian Coast Guard / INCOIS / coastal-state agencies | Local replay-based investigation dashboard | Government innovation grant or institutional pilot |
| **Operational deployment** | Ports, oil terminals, offshore operators, coastal authorities | Configurable incident-analysis workspace, reports, training, support | Annual institutional licence + support contract |
| **Research edition** | Universities and marine-research labs | Historical-data analysis, teaching, and evaluation tools | Free/low-cost academic access; paid deployment support |

---

## 📚 Research and References

### Competitor Landscape
* **SkyTruth Cerulean (Detection & Monitoring):** Detects suspected oil pollution from satellite imagery. **Gap:** Focuses on detection and monitoring, not forensic source reconstruction.
* **INCOIS OOSA / NOAA GNOME (Forward Drift & Response):** Models where an oil spill is likely to move using environmental data. **Gap:** Primarily supports forward prediction, not vessel-source investigation.
* **OCCURIS — Spill Forensics (Source Reconstruction):** SpillSplit tests whether a spill has one or multiple possible sources. Backward reconstruction estimates the probable origin and release-time window.
* **OCCURIS — Vessel Investigation (Counterfactual Attribution):** Simulates a hypothetical release from candidate vessels and compares it with the observed spill. Tri-Layer AIS separates normal AIS, AIS gaps, and reporting anomalies before prioritizing candidates.

### Key References
1. Zhang et al., 2022 — Deep Learning Based Oil Spill Detector Using Sentinel-1 SAR Imagery.
2. Remote Sensing, 2022 — Oil Spill Detection with Dual-Polarimetric Sentinel-1 SAR.
3. SPIE, 2024 — Combining SAR and AIS to Track Oil Discharge Vessels.
4. Achiri et al., 2018 — Collaborative Use of SAR and AIS Data for Maritime Surveillance.
5. Wolsing et al., 2022 — Anomaly Detection in Maritime AIS Tracks: Review.
6. Ocean Engineering, 2023 — Detection of AIS Message Falsification and Spoofing.