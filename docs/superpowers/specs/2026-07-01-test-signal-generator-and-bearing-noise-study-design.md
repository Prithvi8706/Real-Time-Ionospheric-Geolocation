# Design: Test Signal Generator + Bearing-Noise Sensitivity Study

**Problem ID:** DRDO DIA-CoE/EW/02
**Date:** 2026-07-01
**Status:** Approved design, pending implementation

## 1. Motivation

Two official DRDO deliverables are currently weak or missing in the codebase:

1. **Test signal generation tool** — an explicit deliverable. What exists today
   (`data/simulate_ssl_dataset.py`) runs the solver *forward* over a grid; it does
   not synthesize known-position ground-truth signals that the SSL accuracy can be
   measured against. There is no clean ground-truth generator.
2. **Figure of Merit under realistic bearing error** — the current accuracy figures
   (77 km IRTAM, 112 km storm) are computed on **noise-free angles of arrival**
   (README §4). Real HF DF stations have azimuth/elevation errors of degrees, and in
   SSL geometry elevation error dominates the ground-range error. The single largest
   real-world error source is currently absent from every published number.

This design adds a ground-truth **test signal generator** and a **bearing-noise
sensitivity study** built on top of it, closing both gaps. It measures the SSL
**algorithm's own accuracy** as a function of bearing error — the Figure of Merit the
deliverable asks for.

## 2. Scope and key decisions

- **Same-model isolation (approved):** the observation is synthesized and inverted
  using the *same* hybrid ionospheric model. The only error sources are therefore
  bearing noise + the two-pass/spherical-geometry approximation. This cleanly measures
  the algorithm's intrinsic accuracy. Ionospheric *model* error is already
  characterized separately by the existing MAE tables (`report_table3.py`); bundling it
  in here would conflate two error sources and be harder to defend.
- **2D Gaussian noise grid (approved):** independent zero-mean Gaussian noise on
  azimuth and elevation, with `az_sigma` and `el_sigma` swept on separate axes. This
  demonstrates that elevation error dominates range error while azimuth error mainly
  rotates the fix.
- **Out of scope:** cross-model mismatch study, multi-hop geometry, real emitter
  tracks, storm-population re-validation. Single-hop, mid-latitude India geometry,
  consistent with the rest of the project.

## 3. Components

### 3.1 Test Signal Generator — `data/generate_test_signals.py`

The DRDO "test signal generation tool" deliverable.

**Library function:**

```python
def synthesize_observation(
    emitter_lat, emitter_lon,
    receiver_lat, receiver_lon,
    frequency_mhz, dt, kp, dst,
    irtam_available=False,
) -> ObservationTruth
```

Forward geometry against the real hybrid ionosphere:

1. `ground_range_km` = haversine(receiver, emitter) — the **true** great-circle ground range.
2. `azimuth_deg` = initial great-circle bearing receiver → emitter.
3. bounce point = great-circle **midpoint** between receiver and emitter.
4. query `get_ionosphere` at the midpoint → virtual height `h` (via the same
   `_extract_height` logic the solver uses: ray-traced `virtual_height_km` for PyRayHF,
   else `hmF2`).
5. synthesized true elevation: `elevation_deg = degrees(atan(h / ground_range_km))`
   — the exact inverse of the solver's `ground_distance = h / tan(elevation)`.

Returns a dataclass carrying the known emitter position, receiver, `(azimuth_deg,
elevation_deg, frequency_mhz)`, `ground_range_km`, `virtual_height_km`, `model_used`,
and the conditions `(dt, kp, dst)`.

**CLI run** produces `data/processed/test_signals.csv` for a reproducible emitter set
(`numpy` seed 42): a spread of azimuths (e.g. every 45°) × single-hop ground ranges
(e.g. {800, 1500, 2200} km) × representative 2012 conditions, receiver at AH223
Ahmedabad (23.0°N, 72.6°E). Ranges are chosen to stay within plausible single-hop
skywave geometry and to keep synthesized elevation inside the solver's validated
1°–60° band.

**Elevation-band guard:** emitter geometries whose synthesized true elevation falls
outside 1°–60° (the solver's validated input range) are dropped with a logged count, so
every emitted test signal is a valid solver input.

### 3.2 Bearing-Noise Study — `bearing_noise_study.py` (repo root)

Placed at repo root next to `report_table3.py` (results/simulation script convention).

- Load `data/processed/test_signals.csv` (generate it if absent).
- Grid: `az_sigma ∈ {0, 0.5, 1.0, 2.0}°` × `el_sigma ∈ {0, 0.5, 1.0, 2.0}°` (4×4 = 16 cells).
- Per cell: for each test signal, draw `N` Gaussian noise realizations
  `az' = az + N(0, az_sigma)`, `el' = el + N(0, el_sigma)` (clipped to the valid
  1°–60° elevation band), run the real `ssl_locate`, compute haversine error between
  recovered `(transmitter_lat, transmitter_lon)` and the known emitter.
- Report **MAE / median / P90** per cell. The `(az_sigma=0, el_sigma=0)` cell is the
  algorithm's **intrinsic error floor** (two-pass + spherical approximation only, no noise).
- Output: a 2D MAE table printed to stdout + full per-trial
  `data/processed/bearing_noise_results.csv`.
- Reproducible: fixed `numpy` seed; deterministic across runs.

**Runtime control:** `ssl_locate` makes two real model calls (~1–1.5 s each). The study
installs a **memoizing wrapper** on `get_ionosphere` *inside the study script only*
(monkeypatch of `models.ssl_algorithm.get_ionosphere`; production code untouched),
keyed on coordinates quantized to 0.1° — well below the ionosphere's native spatial
resolution, so physically negligible while collapsing thousands of calls to minutes.
`N` and the emitter count are sized against a measured per-call latency probe so the
full run stays under ~5 minutes. The quantization is documented as a deliberate,
physically-justified optimization.

### 3.3 Results doc — `docs/bearing_noise_results.md`

The 2D MAE table + honest interpretation: intrinsic floor, elevation-vs-azimuth
sensitivity asymmetry, and explicit scope (single-hop, mid-latitude, same-model —
model error characterized separately in `docs/results.md`).

## 4. Data flow

```
generate_test_signals.py
   emitter (known lat/lon) --forward geometry + real iono--> (az, el, freq) truth
   --> data/processed/test_signals.csv

bearing_noise_study.py
   test_signals.csv --inject Gaussian (az_sigma, el_sigma)--> noisy (az', el')
   --> ssl_locate (real, memoized iono) --> recovered (tx_lat, tx_lon)
   --> haversine error vs known emitter --> MAE grid + bearing_noise_results.csv
```

## 5. Testing

Unit tests added to `tests/` — confirm the generator and solver are true inverses
*before* trusting any Monte-Carlo result:

1. **Pure-geometry round trip is exact:** `compute_transmitter_location(rx, az, d)`
   followed by haversine range + initial bearing back to the receiver recovers `az` and
   `d` to floating-point tolerance.
2. **Height/elevation inverse is exact:** `atan(h / (h/tan(el)))` recovers `el`; i.e.
   `synthesize_observation`'s elevation and `compute_ground_distance` are inverses for a
   fixed height.
3. **Zero-noise recovery is bounded:** feeding a synthesized clean observation through
   `ssl_locate` recovers the known emitter within a documented small tolerance
   (the two-pass intrinsic floor) — this test asserts a loose bound, not exactness,
   since the two-pass refinement is an approximation.

The full-pipeline two-pass error magnitude is an **empirical result** reported by the
study, not a unit-test invariant.

## 6. Surgical footprint

- **New:** `data/generate_test_signals.py`, `bearing_noise_study.py`,
  `docs/bearing_noise_results.md`, tests in `tests/`.
- **Unchanged:** `models/ssl_algorithm.py`, `api/main.py`, all model wrappers. The study
  reuses `ssl_locate`, `compute_ground_distance`, `compute_transmitter_location`, and
  `get_ionosphere` exactly as they exist.

## 7. Success criteria

1. `generate_test_signals.py` produces a reproducible `test_signals.csv` of valid
   known-position signals; every row's elevation is within 1°–60°.
2. Unit tests (geometry inverses + bounded zero-noise recovery) pass.
3. `bearing_noise_study.py` runs end-to-end in < ~5 min and emits a 4×4 MAE grid + CSV,
   deterministically reproducible.
4. `docs/bearing_noise_results.md` reports the intrinsic floor and the az/el sensitivity
   asymmetry with honest scope statements.
