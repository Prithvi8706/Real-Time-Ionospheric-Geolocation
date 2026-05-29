# Architecture — Real-Time Ionospheric Geolocation

**Problem ID:** DRDO DIA-CoE/EW/02  
**Version:** 1.0.0 (post-engineering-review; D1–D12 fixes applied)

---

## Overview

The system estimates the geographic location of an HF radio emitter from
a single receiving station. It takes the receiver position, the measured
signal bearing (azimuth) and elevation angle, the signal frequency, and
current geomagnetic conditions as input, and returns a latitude/longitude
estimate for the transmitter along with an uncertainty-quantified GP
correction.

The pipeline has three layers:

1. **Hybrid ionospheric model** — selects the most appropriate physics
   model for the current conditions and returns an ionospheric profile.
2. **Two-pass SSL algorithm** — uses the profile to convert elevation
   angle to ground range via single-station location geometry.
3. **GP correction layer** — applies a Gaussian Process trained on
   real residuals to reduce systematic bias in the SSL estimate.

---

## Layer 1 — Hybrid Ionospheric Model

### Model priority order

The selector in `models/hybrid_selector.py` evaluates four conditions in
strict priority order:

```
1. Storm?         Kp >= 5  OR  Dst <= −100 nT   →  PyRayHF
2. High latitude? |lat| >= 60°                  →  A-CHAIM
3. IRTAM cached?  irtam_available == True        →  IRTAM
4. Fallback                                      →  IRI-2016
```

Each condition is checked exactly once; the first match wins.

**PyRayHF** (storm slot): Invoked when Kp reaches storm threshold (≥ 5)
or the Dst ring-current index falls to −100 nT or below. PyRayHF
ray-traces a virtual height by injecting an IRI electron density profile
into the Appleton-Hartree formulation. The output is a `RayHFProfile`
carrying `virtual_height_km` directly from ray tracing rather than deriving
it from `hmF2`. This distinguishes PyRayHF from all other model branches.
Note: the SAMI3 first-principles physics model is not integrated; PyRayHF
is the storm-time proxy implemented in this slot.

**A-CHAIM v6.0.3** (high-latitude slot): An empirical auroral model from
NRCan. It is invoked only when |lat| ≥ 60°. At the AH223 Ahmedabad
station (23°N), this condition never fires; A-CHAIM is present for
completeness at polar/sub-polar deployments. The model is called as an
external executable; its paths must be set via environment variables
`ACHAIM_EXE_PATH` and `ACHAIM_DB_PATH`.

**PyIRTAM** (assimilated nominal): Uses date-specific ionosonde
assimilation coefficients from the IRTAM archive. It is the highest-quality
model for nominal mid-latitude conditions but requires that local
coefficient files for the requested date are present on disk. The
`irtam_available` flag in the request tells the server whether those files
exist. If IRTAM is selected but `get_irtam_profile()` returns null fields
(missing coefficients, parse failure, etc.), the system falls back to IRI.

**IRI-2016** (calm fallback): The international reference ionosphere.
Used when conditions are calm, IRTAM is unavailable, and latitude is
mid-range. Always available as it depends on no external files beyond the
`iri2016` Python package.

### Runtime fallback

Each non-IRI branch checks whether its wrapper produced a usable profile
before committing to that branch. If the profile is null or incomplete,
`hybrid_model.py` logs a warning and re-queries IRI. This is why
`model_used` and `selected_model` can differ in the response (see D1 below).

---

## Layer 2 — Two-Pass SSL Algorithm

Single-Station Location (SSL) converts a measured elevation angle into a
ground range using the virtual height of the ionospheric F2 layer, then
projects that range along the observed azimuth to produce a transmitter
location.

### Why two ionospheric calls

The ionosphere is not horizontally uniform. The profile at the receiver
location does not represent the conditions at the actual reflection point,
which lies halfway between the receiver and the transmitter. A single call
at the receiver introduces systematic range error.

The two-pass algorithm corrects this:

**Pass 1 — rough estimate (receiver location):**
```
height₁  =  get_ionosphere(receiver_lat, receiver_lon, ...)
distance₁ = height₁ / tan(elevation)
tx₁       = project(receiver, azimuth, distance₁)
```

**Midpoint computation:**
```
mid_lat = (receiver_lat + tx₁_lat) / 2
mid_lon = (receiver_lon + tx₁_lon) / 2
```

**Pass 2 — refined estimate (midpoint = approximate bounce point):**
```
height₂  = get_ionosphere(mid_lat, mid_lon, ...)
distance₂ = height₂ / tan(elevation)
tx_final  = project(receiver, azimuth, distance₂)
```

The midpoint approximates the ionospheric reflection point. Querying the
model there rather than at the receiver captures horizontal gradients in
electron density that would otherwise bias the range estimate.

### Ground-range formula

Classical SSL geometry (flat-Earth approximation for the ionospheric path):

```
ground_distance = virtual_height / tan(elevation_deg)
```

The transmitter location is then computed by moving along the great-circle
path from the receiver at the given azimuth for `ground_distance` km,
using spherical-Earth geometry.

### Virtual height extraction

For PyRayHF profiles the ray-traced `virtual_height_km` is used directly.
For all other profiles (IRTAM, IRI, A-CHAIM), `hmF2` (the height of the
F2 peak) is used as a proxy for virtual height. If the extracted height is
null, zero, or NaN, the API returns HTTP 503 rather than silently producing
a nonsense location (D2 null guard).

### Elevation singularity guard

`tan(0°) = 0`, which would produce infinite ground range. The request
validator enforces `elevation_deg >= 1.0°` to prevent this. Values above
60° are also rejected because near-vertical incidence is outside the
typical HF skywave geometry on which the model was validated.

---

## Layer 3 — GP Correction

### What the GP learns

The physics-only SSL estimate carries a systematic bias because the
ionosphere departs from the assumptions built into the SSL formula
(horizontal uniformity, single reflection, no ray bending). This residual
is learnable: given the same geometry and conditions, the bias tends to
repeat.

The GP is trained on real residuals from the AH223 Ahmedabad ionosonde
data for 2012. Each row records:

- The ten input features: azimuth, elevation, frequency, virtual height,
  Kp, Dst, hour-of-day, month-of-year, SSL-estimated latitude, SSL-estimated
  longitude.
- The residual: the difference between the SSL estimate and the known
  true transmitter location (latitude residual and longitude residual
  separately).

At inference time the GP predicts the expected residual for a new
observation and adds it to the SSL estimate. It also returns a posterior
standard deviation for each predicted residual, which is combined into
`correction_std_km`.

### Per-population routing (D1 fix)

IRTAM and PyRayHF rows have structurally different error patterns. IRTAM
profiles are assimilated and accurate under nominal conditions; their
residuals are small and spatially smooth. PyRayHF residuals under storm
conditions are larger and behave differently. Mixing both populations into
a single GP causes the latitude kernel to collapse (length scale near zero,
noise floor dominates), destroying the correction.

The solution is two separate GP pairs:

| Population | Training rows | `.pkl` files |
|---|---|---|
| IRTAM (nominal) | 7,382 (80% of 9,228) | `gp_lat_irtam.pkl`, `gp_lon_irtam.pkl` |
| PyRayHF (storm) | 183 (80% of 229) | `gp_lat_sami3.pkl`, `gp_lon_sami3.pkl` |

At inference time `apply_gp_correction()` reads `ssl_result.model_used`
and routes to the matching GP pair. IRI and A-CHAIM rows have no GP
population (too few training samples to train reliably); for those branches
the correction is not applied and `gp_correction.status = "not_applied"`.

### `model_used` vs `selected_model` — the D1 audit trail

Two fields appear in every response:

- `selected_model`: the model the selector chose given the input conditions.
- `model_used`: the model that actually produced the ionospheric profile.

These differ when a runtime fallback occurs. For example: conditions are
nominal, `irtam_available = true`, so the selector chooses IRTAM
(`selected_model = "IRTAM"`). But the local coefficient files for that
date are missing, so `get_irtam_profile()` returns null fields and the
code falls back to IRI (`model_used = "IRI"`).

The GP correction must route on `model_used`, not `selected_model`. Before
the D1 fix, both fields were set to the same value; fallbacks were silent
and the GP routed on the wrong population. The fix separated the two
fields throughout the pipeline.

### OOD warning

The GP was trained on three months of 2012 data at the AH223 station
(23°N, 72°E). Requests that fall outside this distribution receive an
`ood_warning = true` flag. The check examines:

- Month: must be June (6), July (7), or December (12).
- Transmitter latitude: must be between 15°N and 35°N.

Note: the OOD check runs on the estimated transmitter latitude
(`ssl_result.transmitter_lat`), not the receiver latitude. The GP was
trained on `baseline_lat` (the SSL estimate of transmitter position), so
that is the correct variable to check (D11 fix).

### D12 — MUF warning

`foF2` (the critical frequency of the F2 layer) is extracted from the
ionospheric profile used in the second SSL pass and returned to the API
layer. If `frequency_mhz > foF2`, the signal frequency exceeds the
maximum usable frequency for reflection. The signal will likely penetrate
the ionosphere rather than reflect, making the SSL geometry invalid.
When this occurs, `muf_warning = true` is set in the response and a note
is appended to `gp_correction.note`.

---

## D2 — Null profile guard

Before the D2 fix, a null height from any ionospheric model would propagate
silently into `compute_ground_distance()`, causing a `TypeError` or an
infinite location estimate with no useful error message. The fix introduces
`_extract_height()` in `ssl_algorithm.py`, which raises `HTTPException(503)`
immediately if the height is null, NaN, or non-positive. This surfaces the
failure cleanly during live demos instead of returning a 500 traceback.

---

## Component map

```
api/main.py
│
├── POST /locate
│   ├── ssl_locate()                    ← models/ssl_algorithm.py
│   │   ├── get_ionosphere() × 2        ← models/hybrid_model.py
│   │   │   ├── select_model()          ← models/hybrid_selector.py
│   │   │   ├── get_iri_profile()       ← models/iri/iri_wrapper.py
│   │   │   ├── get_irtam_profile()     ← models/irtam/irtam_wrapper.py
│   │   │   ├── get_achaim_profile()    ← models/achaim/achaim_wrapper.py
│   │   │   └── get_rayhf_profile()     ← models/rayhf/rayhf_wrapper.py
│   │   └── compute_ground_distance()
│   │       compute_transmitter_location()
│   └── apply_gp_correction()           ← routes on model_used
│       ├── gp_lat_irtam / gp_lon_irtam ← models/saved/gp_lat_irtam.pkl …
│       └── gp_lat_sami3 / gp_lon_sami3 ← models/saved/gp_lat_sami3.pkl …
│
├── GET /health
└── GET /  → api/static/index.html
```

---

## Static asset delivery (H2)

The Leaflet map library (CSS + JS) is bundled in `api/static/` and served
from the FastAPI `StaticFiles` mount. This removes the CDN dependency that
was flagged in the H2 security audit. The ops-console UI loads fully
without internet access. Live OpenStreetMap tile imagery still requires
internet unless a local tile server (e.g. TileServer GL with a `.mbtiles`
file) is substituted in `index.html`.
