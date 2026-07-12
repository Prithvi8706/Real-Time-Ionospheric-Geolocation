# Real-Time Ionospheric Geolocation — DRDO DIA-CoE/EW/02

## 1. Introduction and Background

This repository contains the source code and documentation for a research project improving the accuracy of Single Station Location (SSL) for High Frequency (HF) signals. The project targets the research problem statement released by DRDO for its DIA Centres of Excellence (Problem ID: DIA-CoE/EW/02). Built and completed solo after the original team disbanded.

## 2. Problem Statement

The geolocation of HF emitters via skywave propagation is fundamentally limited by the accuracy of the underlying ionospheric model. Existing climatological models (e.g., IRI) fail to account for dynamic, short-term variations in the ionosphere — including solar storms, geomagnetic disturbances, and diurnal changes — leading to significant location errors.

Current operational baseline: bearing-line direction finding only — azimuth and elevation measured, but no range estimate computed. This system adds range estimation via SSL physics and a hybrid ionospheric model, converting a bearing-only measurement into a full lat/lon geolocation estimate.

## 3. Technical Solution

### 3.1 SSL Physics

```
ground_distance = virtual_height / tan(elevation_angle)
```

The receiver measures azimuth and elevation of the incoming HF signal. Virtual height is modelled from the ionosphere at the signal's bounce point (midpoint between receiver and estimated transmitter). Ground distance is then projected along the azimuth over a spherical Earth to produce a transmitter lat/lon estimate.

### 3.2 Hybrid Ionospheric Model

A condition-aware selector routes each query to the most appropriate model:

- **PyRayHF (storm-time ray tracer):** Used for storm conditions (Kp >= 5 or Dst <= -100 nT). Computes virtual height directly via ray tracing through an IRI electron density profile. Note: the SAMI3 first-principles physics model is not integrated in this release — PyRayHF is the storm-time proxy implemented in this slot.
- **A-CHAIM (Advanced Canadian High Arctic Ionospheric Model, v6.0.3):** Used for high-latitude regions (|lat| >= 60°). Built from Canadian, auroral, and Arctic observational data. Requires Windows executable — configured via `ACHAIM_EXE_PATH` and `ACHAIM_DB_PATH` environment variables.
- **IRTAM (IRI-based Real-Time Assimilative Model):** Primary model for nominal mid-latitude conditions where ionosonde data is available. Provides real-time corrections over the IRI baseline using locally cached GIRO coefficient files (`download=False`).
- **IRI-2016 (International Reference Ionosphere):** Fallback model for calm, mid-latitude conditions. Globally available and reliable under stable conditions. IRI-2020 upgrade identified as future work (Fortran toolchain unavailable on current deployment platform).

### 3.3 Two-Pass SSL Algorithm

Each geolocation query runs two ionospheric model calls:
1. Query at receiver location → rough ground distance → rough transmitter location
2. Query at midpoint (ionospheric bounce point) → final ground distance → final transmitter location

This correctly samples the ionosphere at the physical reflection point rather than the receiver.

### 3.4 GP Correction Layer

A Gaussian Process correction layer learns the residual error structure between SSL physics estimates and true transmitter locations. Two separate GP pairs (latitude and longitude) are trained per model population:

- **IRTAM population:** 9,228 rows — GP trained on real AH223 ionosonde residuals
- **PyRayHF storm population:** 66 rows — GP trained on storm-time residuals ray-traced at the request frequency (D8 fix). Of the 229 storm-condition rows, 163 penetrate the ionosphere at their drawn frequency (no skywave return) and fall back to IRI, where no GP applies.

Features: azimuth, elevation, frequency, virtual height, Kp, Dst, hour, month, baseline lat/lon.

**Training distribution bounds:** AH223 station (Ahmedabad, 23°N 72°E), June/July/December 2012, single-hop simulated emitter geometry. GP correction reliability is reduced outside this distribution — the API flags out-of-distribution inputs via `ood_warning` in the response.

**Note on dataset labels:** Storm-condition rows in `data/processed/ssl_real_residuals_2012.csv` were regenerated after the D8 fix (`data/regen_storm_residuals.py`) and carry `PyRayHF`/`IRI` labels; the GP training script (`models/ssl_gp_model.py`) also still accepts the legacy `SAMI3` label from pre-regeneration CSVs.

## 4. Validated Results

All figures are evaluated on held-out test folds (random 80/20 split per population, `random_state=42`). IRTAM test fold: n = 1,846 of 9,228 total rows. Storm test fold: n = 14 of 66 total rows. The storm test fold is very small; storm-time figures should be read accordingly.

| Population | Total rows | Test fold (n) | Baseline MAE | GP-Corrected MAE | Improvement |
|---|---|---|---|---|---|
| IRTAM | 9,228 (97.6%) | 1,846 | 103.29 km | 77.15 km | 26.14 km (25.3%) |
| PyRayHF (storm) | 66 (0.7%) | 14 | 405.90 km | 379.64 km | 26.26 km (6.5%) |

**Error distribution (held-out test folds):**

| Statistic | IRTAM baseline | IRTAM corrected | Storm baseline | Storm corrected |
|---|---|---|---|---|
| Median | 62.20 km | 52.23 km | 286.38 km | 247.03 km |
| P90 | 249.55 km | 170.36 km | 904.06 km | 861.86 km |
| Worst case | 1,012.35 km | 681.78 km | 1,147.55 km | 1,304.26 km |

**Revision note (D8, 2026-07-11):** Storm figures published before this date (baseline 610.80 km → corrected 111.96 km, 81.7%) were computed with PyRayHF ray-tracing at a fixed 5 MHz and a shape misuse of `find_vh` that returned a per-layer value instead of the vertical group-refractive-index integral. The large "learnable" storm bias the old GP removed was substantially that artifact. With the corrected physics: 163 of 229 storm-condition rows penetrate at their drawn frequency (correctly no skywave return → IRI fallback + MUF warning path), the remaining 66-row PyRayHF population has a 405.90 km baseline, and the retrained GP improves it only marginally (6.5%; the longitude kernel collapses on 52 training rows). Growing the storm population is the top validation priority.

**Scope:** These figures are held-out test-fold performance within the training distribution (single-hop, mid-latitude India, Jun/Jul/Dec 2012, simulated emitter geometry, noise-free angles of arrival). The split is random at row level; a stricter day-blocked variant (`day_blocked_split.py`, no calendar day in both folds) degrades the IRTAM correction only modestly — 83.14 km MAE (23.0%) vs 77.15 km (25.3%) — so the headline is not an artifact of temporal leakage. Generalisation to other months, latitudes, or real emitter geometries is not validated.

**Reproducibility:** All figures above reproduce deterministically. From the repo root:

```powershell
& "C:\Users\prith\anaconda3\python.exe" report_table3.py
```

This loads the archived models from `models/saved/` and recomputes Tables 2 and 3 without retraining (~1 minute).

## 5. Repository Structure

```
Real-Time-Ionospheric-Geolocation/
├── api/
│   ├── main.py                     # FastAPI service — /locate, /health, /
│   └── static/
│       └── index.html              # Dark ops-console UI with Leaflet map
├── data/
│   ├── fetch_omni.py               # NASA OMNIWeb space weather fetcher
│   ├── merge_indices.py            # AH223 + OMNI merge pipeline
│   ├── generate_real_residuals.py  # Full SSL residual run (~125 min)
│   └── processed/                  # Merged datasets (gitignored, large)
├── models/
│   ├── hybrid_model.py             # Master ionospheric model router
│   ├── hybrid_selector.py          # Condition-aware model selector
│   ├── ssl_algorithm.py            # Two-pass SSL geolocation
│   ├── ssl_gp_model.py             # Per-population GP training (80/20 split, seed 42)
│   ├── iri/                        # IRI-2016 wrapper
│   ├── irtam/                      # PyIRTAM wrapper (local cache)
│   ├── achaim/                     # A-CHAIM v6.0.3 wrapper
│   ├── rayhf/                      # PyRayHF storm-time ray tracer
│   └── saved/                      # Trained GP model files (.pkl)
├── notebooks/
│   └── exploration.ipynb           # Residual analysis and error comparison
├── graphify-out/
│   ├── graph.html                  # Interactive knowledge graph
│   └── GRAPH_REPORT.md             # Graph analysis report
├── report_table3.py                # Reproduces Tables 2–3 from archived models (no retraining)
├── requirements.txt
└── README.md
```

## 6. Setup Instructions

### Requirements

- Windows 11, Anaconda Python 3.12
- scikit-learn 1.5.1 (pinned — GP models serialised under this version)
- PyIRTAM (local installation, case-sensitive import: `import PyIRTAM`)
- PyRayHF (local installation, case-sensitive import: `import PyRayHF`)
- A-CHAIM v6.0.3 Windows executable

### Environment Variables (A-CHAIM)

```powershell
$env:ACHAIM_EXE_PATH = "C:\path\to\A-CHAIM\ACHAIM.exe"
$env:ACHAIM_DB_PATH  = "C:\path\to\A-CHAIM\example.db"
```

A-CHAIM is only invoked for |lat| >= 60°. Mid-latitude demos (receiver at ~23°N) never trigger it.

### Run the API

```powershell
& "C:\Users\prith\anaconda3\python.exe" -m uvicorn api.main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

### Run a test query

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/locate" -ContentType "application/json" -Body '{"receiver_lat":23.0,"receiver_lon":72.0,"azimuth_deg":45.0,"elevation_deg":30.0,"frequency_mhz":10.0,"timestamp":"2012-06-15T12:00:00","kp":2.0,"dst":-20.0,"irtam_available":true}'
```

### Reproduce validation figures (no retraining required)

```powershell
& "C:\Users\prith\anaconda3\python.exe" report_table3.py
```

Runs in under one minute. Reproduces all MAE, median, P90, and worst-case figures from Tables 2–3 of the technical report.

### Regenerate the residual dataset from scratch (~125 min)

```powershell
& "C:\Users\prith\anaconda3\python.exe" data/fetch_omni.py
& "C:\Users\prith\anaconda3\python.exe" data/merge_indices.py
& "C:\Users\prith\anaconda3\python.exe" data/generate_real_residuals.py
```

## 7. Known Limitations and Future Work

- **Single-hop geometry only:** Training dataset contains no multi-hop propagation examples. Mode identification is out of scope; proposed as future work.
- **Geographic scope:** Validated on one station (Ahmedabad, 23°N), three months of 2012 (Solar Cycle 24 peak). Results may not generalise to other latitudes, seasons, or solar cycle phases.
- **Simulated emitter geometry:** Ionosphere and space weather indices are real; emitter positions are simulated (random azimuths/distances, seed 42). No real unknown emitter has been tested.
- **Row-level train/test split:** The 80/20 split is random at row level, not blocked by day. Ionospheric residuals are temporally autocorrelated; day-blocked cross-validation is recommended as future hardening.
- **Small storm test fold:** 46 held-out storm cases. All storm-time figures should be read with this sample size in mind.
- **IRI-2020 deferred:** IRI-2016 in use. IRI-2020 upgrade blocked by Fortran toolchain unavailability on the deployment platform.
- **SAMI3 not integrated:** The storm-time slot uses PyRayHF ray tracing, not the SAMI3 first-principles physics model.
- **No out-of-distribution detection beyond month/latitude:** GP correction may degrade for inputs outside the training distribution. The API returns `ood_warning: true` for known OOD inputs.

## 8. Acknowledgements

This project builds on the foundational work of the IRI working group (Bilitza et al.), the IRTAM development team at the University of Massachusetts Lowell (Galkin et al.), the A-CHAIM team at Natural Resources Canada, and the PyRayHF development team. Space weather indices sourced from NASA OMNIWeb. Ionosonde data from the GIRO AH223 station (Ahmedabad).