
# Research Platform for Real-Time HF Geolocation

## 1. Introduction and Background

This repository contains the source code and documentation for a research project aimed at improving the accuracy of Single Station Location (SSL) for High Frequency (HF) signals. The project is directly motivated by the research problem statements released by the DRDO for its DIA-CoEs (Problem ID: DIA-CoE/EW/02).

## 2. Problem Statement

The geolocation of HF emitters via skywave propagation is fundamentally limited by the accuracy of the underlying ionospheric model. Existing climatological models (e.g., IRI) fail to account for dynamic, short-term variations in the ionosphere, leading to significant location errors. The objective is to develop an ionospheric modeling system that operates in real-time.

## 3. Proposed Technical Solution

This project proposes the development of a **hybrid ionospheric model** served via a Python-based API. The model will synthesize data from three distinct, real-time sources to achieve a comprehensive and dynamic characterization of the ionosphere:

*   **Model 1: IRTAM:** Assimilative model for ground-based ionosonde data.
*   **Model 2: NeQuickG:** GNSS TEC-based model for global and high-latitude coverage.
*   **Model 3: GAIM-FP:** First-principles physics model for predictive capability in data-sparse regions.

## 4. Expected Deliverables

In line with the DRDO requirements, this project aims to produce:

1.  **Ionospheric Model Software:** A functional Python codebase implementing the hybrid model.
2.  **API Endpoint:** A FastAPI server for programmatic access to the model.
3.  **Simulation Results:** Test data and accuracy reports benchmarking the model's performance.
4.  **Technical Report:** Documentation describing the algorithm, architecture, and results.

## 5. Evaluation Criteria (Figures of Merit)

The primary performance metric will be the **end-to-end accuracy of the geolocation algorithm** when using the developed ionospheric model.
