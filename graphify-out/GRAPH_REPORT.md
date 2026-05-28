# Graph Report - .  (2026-05-28)

## Corpus Check
- Corpus is ~23,113 words - fits in a single context window. You may not need a graph.

## Summary
- 205 nodes · 309 edges · 22 communities (16 shown, 6 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_IRI Model Interface|IRI Model Interface]]
- [[_COMMUNITY_Data Pipeline & Residuals|Data Pipeline & Residuals]]
- [[_COMMUNITY_Ionospheric Research Literature|Ionospheric Research Literature]]
- [[_COMMUNITY_FastAPI Geolocation Backend|FastAPI Geolocation Backend]]
- [[_COMMUNITY_Frontend & Project Rationale|Frontend & Project Rationale]]
- [[_COMMUNITY_Gaussian Process Correction|Gaussian Process Correction]]
- [[_COMMUNITY_IRTAM Model Interface|IRTAM Model Interface]]
- [[_COMMUNITY_PyRayHF Storm Model|PyRayHF Storm Model]]
- [[_COMMUNITY_Space Weather Data (OMNI)|Space Weather Data (OMNI)]]
- [[_COMMUNITY_Error Comparison Results|Error Comparison Results]]
- [[_COMMUNITY_Residual Analysis & Storms|Residual Analysis & Storms]]
- [[_COMMUNITY_E-CHAIM High-Latitude Model|E-CHAIM High-Latitude Model]]
- [[_COMMUNITY_Model Profile Registry|Model Profile Registry]]
- [[_COMMUNITY_FastAPI Application Core|FastAPI Application Core]]
- [[_COMMUNITY_Locate Request Schema|Locate Request Schema]]
- [[_COMMUNITY_Locate Response Schema|Locate Response Schema]]
- [[_COMMUNITY_RayHF Init|RayHF Init]]
- [[_COMMUNITY_IRTAM Utility|IRTAM Utility]]
- [[_COMMUNITY_Dependencies|Dependencies]]

## God Nodes (most connected - your core abstractions)
1. `ssl_locate()` - 27 edges
2. `get_ionosphere()` - 21 edges
3. `SSLResult` - 10 edges
4. `apply_gp_correction()` - 9 edges
5. `select_model()` - 9 edges
6. `train_gp()` - 9 edges
7. `Forsythe et al. (2023) PyIRI Paper` - 9 edges
8. `Hybrid Ionospheric Model (Condition-Aware Selector)` - 9 edges
9. `IRIProfile` - 8 edges
10. `get_irtam_profile()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `SSL Confidence Map (Folium/Leaflet HTML Output)` --semantically_similar_to--> `Leaflet.js Interactive Map in Frontend`  [INFERRED] [semantically similar]
  notebooks/ssl_confidence_map.html → api/static/index.html
- `str` --uses--> `SSLResult`  [INFERRED]
  api/main.py → models/ssl_algorithm.py
- `SSLResult` --uses--> `SSLResult`  [INFERRED]
  api/main.py → models/ssl_algorithm.py
- `POST /locate Endpoint` --calls--> `ssl_locate()`  [EXTRACTED]
  api/main.py → models/ssl_algorithm.py
- `train_gp()` --shares_data_with--> `GP Models (gp_lat, gp_lon) Loaded via joblib`  [INFERRED]
  models/ssl_gp_model.py → api/main.py

## Hyperedges (group relationships)
- **SSL Geolocation Core Pipeline** — models_ssl_algorithm_ssl_locate, models_hybrid_model_get_ionosphere, models_hybrid_selector_select_model, api_main_locate_endpoint [EXTRACTED 0.95]
- **Real Residual Data Pipeline (OMNI -> AH223 -> SSL Residuals -> GP Training)** — data_fetch_omni_fetch_year, data_merge_indices_main, data_generate_real_residuals_main, models_ssl_gp_model_train_gp [INFERRED 0.95]
- **Ionospheric Model Fallback Chain (SAMI3 -> ACHAIM -> IRTAM -> IRI)** — models_rayhf_rayhf_wrapper_get_rayhf_profile, models_achaim_achaim_wrapper_get_achaim_profile, models_irtam_irtam_wrapper_get_irtam_profile, models_iri_iri_wrapper_get_iri_profile [EXTRACTED 0.95]
- **IRTAM EDP Computation Pipeline** — pyirtam_run_pyirtam, pyirtam_call_irtam_pyiri, pyirtam_edp_builder, pyirtam_gamma, pyirtam_read_coeff [INFERRED 0.85]
- **Hybrid Ionospheric Model Selection System** — readme_hybrid_model, readme_irtam_role, readme_iri_role, readme_echaim_role, readme_sami3_role [EXTRACTED 0.95]
- **SSL Geolocation Frontend-Backend-Simulation Stack** — api_index_html, api_locate_endpoint, sim_ssl_locate_call, sim_output_csv [INFERRED 0.75]
- **IRI Baseline vs GP Corrected Error Comparison** — geolocation_error_comparison_iri_baseline, geolocation_error_comparison_gp_corrected, geolocation_error_comparison_2012_data [EXTRACTED 1.00]
- **Geolocation Error Time Series and Distribution Visualization** — geolocation_error_comparison_timeseries, geolocation_error_comparison_distribution, geolocation_error_comparison_iri_baseline, geolocation_error_comparison_gp_corrected [EXTRACTED 1.00]
- **IRI Residual Analysis: Time Series and Distribution** — residual_analysis_timeseries, residual_analysis_histogram, concept_hmf2_residual, concept_iri_model [EXTRACTED 1.00]
- **Ionospheric Storm Residual Characterization** — concept_ionospheric_storm, concept_hmf2_residual, concept_iri_bias, concept_residual_gp [INFERRED 0.75]

## Communities (22 total, 6 thin omitted)

### Community 0 - "IRI Model Interface"
Cohesion: 0.10
Nodes (29): get_iri_profile(), IRIProfile, is_calm_region(), IRI (International Reference Ionosphere) Wrapper Used as fallback model for calm, Stores IRI model output for a given location and time., Query IRI model for ionospheric parameters at given location and time.      Args, Determine if ionospheric conditions are calm enough to use IRI as fallback., get_achaim_hmf2 Function (+21 more)

### Community 1 - "Data Pipeline & Residuals"
Cohesion: 0.11
Nodes (22): haversine_km(), main(), project_location(), main(), main(), simulate_ssl_dataset Script (Synthetic Data Generator), main(), main() (+14 more)

### Community 2 - "Ionospheric Research Literature"
Cohesion: 0.16
Nodes (20): Bilitza et al. (2022) IRI Review Paper, Forsythe et al. (2023) PyIRI Paper, Galkin et al. (2015) GAMBIT Database Paper, Jones & Gallet (1965) Ionospheric Numerical Mapping Paper, Jones, Graham & Leftin (1966) Ionospheric Mapping Paper, call_IRTAM_PyIRI Function, IRTAM_density Function, IRTAM_diurnal_functions Function (+12 more)

### Community 3 - "FastAPI Geolocation Backend"
Cohesion: 0.21
Nodes (15): apply_gp_correction(), GPCorrection, IonosphereInfo, locate(), POST /locate Endpoint, LocateRequest, LocateResponse, PrimaryEstimate (+7 more)

### Community 4 - "Frontend & Project Rationale"
Cohesion: 0.14
Nodes (19): GP Correction Display (Experimental), RTIL-GEO Web Frontend (index.html), Leaflet.js Interactive Map in Frontend, /locate API Endpoint (POST), DRDO DIA-CoE/EW/02 Problem Motivation, E-CHAIM Role: High-Latitude Auroral Model, Hybrid Ionospheric Model (Condition-Aware Selector), IRI Role: Calm Mid-Latitude Fallback (+11 more)

### Community 5 - "Gaussian Process Correction"
Cohesion: 0.18
Nodes (16): GP Models (gp_lat, gp_lon) Loaded via joblib, SSL Real Residuals Dataset (2012), build_kernel(), _evaluate(), haversine_error_km(), load_and_prepare(), str, Train per-population GPs — one pair for IRTAM rows, one pair for SAMI3 rows. (+8 more)

### Community 6 - "IRTAM Model Interface"
Cohesion: 0.22
Nodes (13): get_irtam_profile(), IRTAMProfile, is_calm_region(), is_irtam_available(), _nmf2_to_fof2_mhz(), PyIRTAM Wrapper — local installation (no HTTP, no CCMC).  Wraps the locally-inst, True only if the model produced both foF2 and hmF2., Calm geomagnetic conditions test (unchanged from prior contract). (+5 more)

### Community 7 - "PyRayHF Storm Model"
Cohesion: 0.24
Nodes (10): bool, datetime, float, get_rayhf_profile(), is_rayhf_available(), PyRayHF Virtual Height Wrapper Used for storm-time rows (kp >= 5 or dst <= -100), Return True only if the profile contains a usable virtual height., Stores PyRayHF output for a given location and time. (+2 more)

### Community 8 - "Space Weather Data (OMNI)"
Cohesion: 0.36
Nodes (6): fetch_year(), main(), parse_omni2(), main(), AH223 Merged Dataset (Ahmedabad hmF2 + OMNI), OMNI Indices Dataset (2012-2013)

### Community 9 - "Error Comparison Results"
Cohesion: 0.43
Nodes (8): 2012 Geolocation Dataset (Jun-Dec), Geolocation Error Distribution Histogram, GP Corrected Geolocation Error, Gaussian Process Correction Model, IRI Baseline Geolocation Error, IRI Ionospheric Model, Geolocation Error Comparison Figure, Geolocation Error Time Series over 2012

### Community 10 - "Residual Analysis & Storms"
Cohesion: 0.36
Nodes (8): hmF2 Residual (measured minus IRI prediction), Ionospheric Storm Events (2012-06, 2012-12), IRI Model Systematic Bias in hmF2, IRI (International Reference Ionosphere) Model, Residual Gaussian Process Correction, Residual Distribution Histogram, IRI Residual Analysis Figure (2012), IRI hmF2 Residual Time Series (2012-06 to 2013-01)

### Community 11 - "E-CHAIM High-Latitude Model"
Cohesion: 0.43
Nodes (5): get_achaim_hmf2(), get_achaim_profile(), achaim_wrapper.py ================= Wrapper for the A-CHAIM C executable used in, Convenience wrapper matching hybrid_model.py interface., Query A-CHAIM for ionospheric characteristics at a single lat/lon point.      Re

### Community 12 - "Model Profile Registry"
Cohesion: 0.67
Nodes (3): IRIProfile Dataclass, IRTAMProfile Dataclass, RayHFProfile Dataclass

## Knowledge Gaps
- **23 isolated node(s):** `float`, `bool`, `bool`, `bool`, `float` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_ionosphere()` connect `IRI Model Interface` to `Data Pipeline & Residuals`, `E-CHAIM High-Latitude Model`, `IRTAM Model Interface`, `PyRayHF Storm Model`?**
  _High betweenness centrality (0.464) - this node is a cross-community bridge._
- **Why does `ssl_locate()` connect `Data Pipeline & Residuals` to `IRI Model Interface`, `FastAPI Geolocation Backend`?**
  _High betweenness centrality (0.389) - this node is a cross-community bridge._
- **Why does `PyIRTAM Library (lib.py)` connect `Ionospheric Research Literature` to `IRTAM Model Interface`?**
  _High betweenness centrality (0.252) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SSLResult` (e.g. with `GPCorrection` and `IonosphereInfo`) actually correct?**
  _`SSLResult` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Real-Time Ionospheric Geolocation — FastAPI service. DRDO Problem ID: DIA-CoE/EW`, `Apply the GP residual correction as a secondary, experimental step.`, `Master function — selects the right model and returns ionospheric profile.` to the rest of the system?**
  _64 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `IRI Model Interface` be split into smaller, more focused modules?**
  _Cohesion score 0.0967741935483871 - nodes in this community are weakly interconnected._
- **Should `Data Pipeline & Residuals` be split into smaller, more focused modules?**
  _Cohesion score 0.11083743842364532 - nodes in this community are weakly interconnected._