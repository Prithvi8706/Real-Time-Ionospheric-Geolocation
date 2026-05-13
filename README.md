# Research Platform for Real-Time HF Geolocation

## 1. Introduction and Background
This repository contains the source code and documentation for a research project aimed at improving the accuracy of Single Station Location (SSL) for High Frequency (HF) signals. The project is directly motivated by the research problem statements released by the DRDO for its DIA-CoEs (Problem ID: DIA-CoE/EW/02).

## 2. Problem Statement
The geolocation of HF emitters via skywave propagation is fundamentally limited by the accuracy of the underlying ionospheric model. Existing climatological models (e.g., IRI) fail to account for dynamic, short-term variations in the ionosphere — including solar storms, geomagnetic disturbances, and diurnal changes — leading to significant location errors. The objective is to develop an ionospheric modeling system that operates in or near real-time and accounts for these missing parameters.

## 3. Proposed Technical Solution
This project proposes a **hybrid ionospheric model** served via a Python-based API. Rather than relying on a single model, the system uses a condition-aware selector that dynamically routes to the most appropriate model based on geographic region, ionosonde data availability, and space weather conditions:

- **IRTAM (IRI-based Real-Time Assimilative Model):** Primary model where ionosonde data is available. Provides real-time corrections over the IRI baseline using ground-based measurements.
- **IRI (International Reference Ionosphere):** Fallback model for calm, mid-latitude regions without ionosonde coverage. Globally available and reliable under stable conditions.
- **E-CHAIM (Empirical Canadian High Arctic Ionospheric Model):** Deployed for high-latitude and auroral regions where IRI breaks down. Built from Canadian, auroral, and Arctic observational data.
- **SAMI3 (Sami3 is Also a Model of the Ionosphere):** Physics-based first-principles model for harsh conditions such as solar storms and geomagnetic disturbances. Uses plasma physics equations, solar EUV flux, and electric/magnetic field inputs — making it independent of ground station availability.

The hybrid selector logic ensures the most accurate model is always used for a given set of conditions, combining the strengths of each model while compensating for their individual limitations.

## 4. Repository Structure

```
hf-df-geolocation/
├── data/
│   ├── raw/               # Madrigal API pulls, NOAA space weather
│   └── processed/         # Cleaned and formatted data
├── models/
│   ├── iri/               # IRI baseline wrapper
│   ├── irtam/             # IRTAM real-time integration
│   ├── echaim/            # E-CHAIM high-latitude model
│   └── sami3/             # SAMI3 physics-based model
├── hybrid/
│   ├── selector.py        # Condition-aware model routing
│   ├── corrector.py       # ML correction layer
│   └── pipeline.py        # End-to-end geolocation pipeline
├── api/
│   └── main.py            # FastAPI endpoint
├── ml/
│   └── train.py           # ML model training
├── notebooks/
│   └── exploration.ipynb  # Data exploration and visualization
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```

## 5. Expected Deliverables
In line with the DRDO requirements, this project aims to produce:
1. **Ionospheric Model Software:** A functional Python codebase implementing the hybrid model with condition-aware selection logic.
2. **API Endpoint:** A FastAPI server for programmatic access to the geolocation pipeline.
3. **Simulation Results:** Test data and accuracy reports benchmarking the hybrid model against vanilla IRI+SSL.
4. **Technical Report:** Documentation describing the algorithm, architecture, and results.

## 6. Evaluation Criteria (Figures of Merit)
The primary performance metric will be the **end-to-end geolocation accuracy** of the algorithm when using the hybrid ionospheric model, benchmarked against the IRI-only baseline. Secondary metrics include performance under disturbed ionospheric conditions and coverage across geographic regions.

## 7. Acknowledgements
This project builds on the foundational work of the IRI working group, the IRTAM development team at the University of Massachusetts Lowell, the E-CHAIM team at Natural Resources Canada, and the SAMI3 team at the US Naval Research Laboratory.