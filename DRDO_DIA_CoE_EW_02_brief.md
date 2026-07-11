# DRDO DIA-CoE/EW/02 — Problem Statement vs. Current Build

## Official Problem Statement (verbatim structure)

- **Technology Area:** Electronic Warfare
- **Technology Category:** COMINT
- **Research Problem:** In HF Direction Finding stations, geolocation of distant HF transmitters must be carried out using estimated Azimuth and Elevation bearings, assuming Ionospheric (Sky Wave) propagation. The Virtual Height of the ionospheric layer that causes total internal reflection depends on location, time of day, season, sunspot number, and signal frequency. Scope of work: identify and procure Ionospheric Model Software, then use Frequency, Azimuth Bearing, Elevation Bearing, and Virtual Height (from the ionospheric model) to estimate the geolocation of the HF transmitter.
- **Major Objective:** Development of a Single Station Location (SSL) Algorithm for HF DF using Azimuth Bearing, Elevation Bearing, and Ionospheric Model Software.
- **Expected Deliverables:** Ionospheric Model Software, Simulation Results with execution-time profiling, a test signal generation tool, Technical Report, and Geolocation Algorithm Description (with computational requirements and code).
- **Figure of Merit:** Accuracy of Single Station Location of HF Emitter.

## What you've already built (satisfies part of this)

| DRDO Ask | Status | Evidence |
|---|---|---|
| Ionospheric Model Software | ✅ Done | Hybrid stack: PyIRTAM → A-CHAIM → IRI-2016 fallback, with per-population GP correction |
| Simulation Results | ✅ Partial | Validated MAE on AH223 Ahmedabad 2012 data: IRTAM 103.29→77.15 km (25.3% improvement), PyRayHF storm case 610.80→111.96 km (81.7% improvement) |
| Technical Report | ✅ Done | DRDO Technical Documentation PDF completed |
| Backend/serving layer | ✅ Done | FastAPI service, Python 3.12, Leaflet dark UI for visualization |

**Important caveat to hold onto:** those MAE numbers are *interpolation* performance on the AH223 dataset, not demonstrated generalization to new stations/dates. Worth flagging honestly in the report rather than overstating it — DRDO reviewers will test generalization.

## What's actually still missing — this is the real gap

The core deliverable — the **Single Station Location (SSL) Algorithm** itself — is not yet built. You have the ionospheric model (Virtual Height source) but not the geometric machinery that turns `(Azimuth, Elevation, Frequency, Virtual Height)` into a lat/lon fix. Three concrete pieces, ~2–3 weeks total:

1. **Bearing input interface** — a way to feed in Azimuth + Elevation bearings (either simulated or from real/test signals) as the SSL algorithm's input.
2. **Virtual height lookup integration** — wire the existing ionospheric model stack into the SSL pipeline so it returns virtual height for a given (lat, lon, time, frequency) query on demand, rather than only being used for standalone validation.
3. **Geometric solver** — the actual single-station geolocation math: given a DF station's known position, an azimuth bearing, an elevation angle, and a virtual reflection height, solve for the ground-range/great-circle distance to the emitter (classic "triangle" geometry: station height, virtual height, elevation angle → ground range; azimuth → bearing direction) and project to a lat/lon.

**Also explicitly listed as a deliverable but not yet started:** a **test signal generation tool** — something that synthesizes known-position "ground truth" HF signals (with realistic azimuth/elevation/frequency) so the SSL algorithm's accuracy (the Figure of Merit) can be measured against a known answer, not just validated on ionospheric MAE alone.

## Suggested build order for Claude Code

1. Geometric solver first (pure math, no dependencies) — implement classic single-station HF geolocation geometry, unit test against hand-calculated cases.
2. Wire virtual-height lookup as a callable function/endpoint from the existing model stack.
3. Build the bearing input interface (accepts az/el/freq, calls virtual height lookup, calls solver, returns lat/lon).
4. Build the test signal generator last, since it needs the solver to exist in order to validate against.
5. Re-run "Simulation Results" against the test signal tool → this gives you real Figure-of-Merit accuracy numbers (not just ionospheric MAE), which is what the deliverable actually asks for.

## Repo context
- Project root: `C:\Users\prith\Real-Time-Ionospheric-Geolocation`
- Python: `C:\Users\prith\anaconda3\python.exe`
- Stack: Python 3.12, FastAPI, Leaflet dark UI
