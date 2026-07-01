# Project Walkthrough — Real-Time Ionospheric Geolocation

**DRDO DIA-CoE/EW/02 — Single Station Location (SSL) for HF emitters**

This document is a from-scratch, plain-language walkthrough of *everything this
project does*, written to get you fully back in tune with it. It is based on the
actual code as it stands today, not on any older status note. Read it top to bottom
once and you'll have the whole system in your head again.

---

## 0. The one-paragraph summary

You point an HF direction-finding (DF) receiver at the sky. It measures two angles for
an incoming shortwave signal: **azimuth** (compass bearing) and **elevation** (angle
above the horizon). That alone tells you *which direction* the transmitter is, but not
*how far*. This project adds the "how far." It uses ionospheric physics — the signal
bounced off a charged layer of the upper atmosphere at some **virtual height** — to turn
the elevation angle into a ground distance, then projects that distance along the azimuth
over a spherical Earth to produce a full **latitude/longitude fix** for the transmitter.
The hard part is knowing the virtual height accurately, because the ionosphere changes
with time of day, season, solar activity, and magnetic storms. So the project wires
together **four ionospheric models** (picking the right one per condition) and adds a
**machine-learning correction layer** trained on real ionosonde data to shave down the
systematic error. It's all exposed as a small web service with a live map.

---

## 1. The problem, in physical terms

### 1.1 Why HF geolocation is weird

HF (High Frequency, 3–30 MHz — shortwave radio) travels enormous distances by
**skywave propagation**: the signal goes up, hits the **ionosphere** (a layer of the
atmosphere ionised by the sun, roughly 100–500 km up), and is refracted back down to
Earth, often hundreds or thousands of km away. This is how shortwave radio crosses oceans.

A direction-finding station can measure the **angle of arrival** of that skywave:
- **Azimuth** — the compass direction the signal came from (0–360°).
- **Elevation** — how steeply it came down from the sky (degrees above horizon).

But a bearing is just a *line*, not a *point*. Classic DF needs two or more stations to
triangulate. **Single Station Location (SSL)** is the trick of getting a full position
from *one* station — by using the elevation angle plus knowledge of how high the signal
bounced.

### 1.2 The "virtual height" idea

When a radio wave refracts through the ionosphere, it doesn't reflect off a hard mirror —
it curves gradually through a region of increasing electron density. But geometrically you
can pretend it bounced off a flat mirror at a certain height. That equivalent mirror
height is the **virtual height**. If you know it, simple triangle geometry gives you the
ground distance. The entire accuracy of SSL hinges on knowing the virtual height at the
signal's bounce point — and that's exactly what the ionosphere makes hard, because it
changes constantly.

That is the DRDO problem statement in a nutshell: *identify ionospheric model software,
then use Frequency + Azimuth + Elevation + Virtual Height to estimate the emitter's
geolocation.*

---

## 2. The core physics (the SSL "triangle")

The single most important line of code in the whole project is this (`models/ssl_algorithm.py`):

```
ground_distance = virtual_height / tan(elevation_angle)
```

Picture a right triangle:
- The **vertical side** is the virtual height `h` (the mirror in the sky).
- The **elevation angle** is the angle the incoming ray makes with the ground.
- The **horizontal side** is the ground distance to the bounce point.

Because it's a right triangle, `tan(elevation) = h / ground_distance`, which rearranges to
the formula above. (For a single-hop signal, the transmitter is at roughly this ground
distance from the receiver — the geometry assumes the bounce point is at the midpoint, so
the full hop is receiver → bounce → transmitter.)

Then, to turn a distance-and-bearing into an actual lat/lon, the code walks that distance
along the azimuth over a sphere using the standard **great-circle destination formula**
(`compute_transmitter_location`):

```python
lat2 = arcsin( sin(lat1)·cos(d) + cos(lat1)·sin(d)·cos(azimuth) )
lon2 = lon1 + arctan2( sin(azimuth)·sin(d)·cos(lat1),
                       cos(d) − sin(lat1)·sin(lat2) )
```

where `d = ground_distance / Earth_radius` (angular distance). That's it — that's the
geolocation math. Everything else in the project exists to feed this triangle a *good
virtual height*.

---

## 3. What happens on a single request (end to end)

When you POST to `/locate` with `{receiver, azimuth, elevation, frequency, timestamp, kp,
dst, ...}`, here is the exact chain of events:

1. **API validation** (`api/main.py`, `LocateRequest`) — Pydantic validators reject
   nonsense before any physics runs: elevation must be 1–60°, frequency 2–30 MHz (the HF
   band), azimuth 0–360°, kp 0–9, dst −500…50 nT, f107 50–300 SFU, lat/lon in range,
   timestamp must be ISO-8601. The elevation floor of 1° matters: `tan(elevation)` blows up
   near 0°, so tiny elevations would produce absurd distances.

2. **SSL solve, pass 1 — rough** (`ssl_locate`): query the ionospheric model **at the
   receiver's own location**, get a virtual height, compute a rough ground distance, and
   project a rough transmitter location along the azimuth.

3. **Find the bounce point**: the signal didn't actually bounce over the receiver — it
   bounced roughly halfway between the receiver and the transmitter. So the code takes the
   **midpoint** between the receiver and the rough transmitter estimate.

4. **SSL solve, pass 2 — refined**: query the ionosphere **again, at that midpoint**
   (the physical reflection point), get a better virtual height, recompute the ground
   distance, and project the **final** transmitter location. This is the "two-pass"
   algorithm — it samples the ionosphere where the bounce really happens, not over the
   receiver.

5. **GP correction** (`apply_gp_correction`): the physics estimate has a known systematic
   bias. A trained Gaussian Process model predicts that bias and nudges the estimate toward
   the truth, and also reports its own uncertainty. This is a *secondary, clearly labelled*
   output — the headline number is always the raw physics estimate.

6. **MUF sanity check**: if the requested frequency exceeds `foF2` (the ionosphere's
   critical frequency), the signal would punch *through* the ionosphere instead of
   reflecting — so no skywave path exists and the estimate is flagged unreliable
   (`muf_warning`).

7. **Response**: a structured JSON with `primary_estimate` (physics), `ionosphere`
   (which model was used and why), `gp_correction` (the corrected fix + uncertainty +
   out-of-distribution warning), and `muf_warning`.

---

## 4. The hybrid ionospheric model (the heart of the system)

Step 2/4 above says "query the ionospheric model." There isn't *one* model — there's a
router that picks the best of four depending on conditions. This is
`models/hybrid_model.py` (the dispatcher) and `models/hybrid_selector.py` (the decision
logic).

### 4.1 The selection logic (`select_model`)

The rules, checked in priority order:

| Priority | Condition | Model chosen | Why |
|---|---|---|---|
| 1 | `kp ≥ 5` **or** `dst ≤ −100 nT` | **PyRayHF** | Geomagnetic storm — the ionosphere is violently disturbed; use a ray tracer. |
| 2 | `|latitude| ≥ 60°` | **A-CHAIM** | Polar/auroral zone — needs a specialised high-latitude model. |
| 3 | otherwise, if IRTAM data available | **IRTAM** | Nominal mid-latitude — use the real-time assimilated model. |
| 4 | otherwise | **IRI** | Calm fallback — the reliable climatological baseline. |

- **Kp** is the planetary geomagnetic activity index (0 calm … 9 extreme storm).
- **Dst** is the storm-ring-current index in nanotesla (near 0 calm, strongly negative = storm).

### 4.2 The four models

**IRI-2016 (International Reference Ionosphere)** — `models/iri/iri_wrapper.py`
The gold-standard *climatology*: a decades-old empirical model giving the average
ionosphere for any place/time. Reliable but it's an *average* — it can't know about
today's specific disturbances. Used as the universal fallback and as the electron-density
input for PyRayHF. Note: it only covers ~1958–2020 (it returns a sentinel for later dates,
which the wrapper catches). Provides `hmF2` (peak height), `NmF2` (peak density), `foF2`
(critical frequency), `TEC`.

**IRTAM (IRI Real-Time Assimilative Model)** — `models/irtam/irtam_wrapper.py`
IRI, but corrected in near-real-time by assimilating actual ground ionosonde measurements.
When it has data for the time/place, it's much better than plain IRI. Runs from locally
cached GIRO coefficient files (`download=False`) so it works offline. This is the primary
model for the project's demo region (mid-latitude India). If it can't produce a usable
profile, the system **falls back to IRI** and records that in the audit trail
(`selected_model=IRTAM`, `model_used=IRI`).

**A-CHAIM (Advanced Canadian High Arctic Ionospheric Model)** — `models/achaim/achaim_wrapper.py`
A specialist for the high Arctic / auroral latitudes where the ionosphere behaves very
differently. It's an external Windows executable, configured via `ACHAIM_EXE_PATH` and
`ACHAIM_DB_PATH` environment variables. **It only ever fires for `|lat| ≥ 60°`, so in any
India-region demo (23°N) it is never triggered** — it's there for deployment completeness
at polar sites.

**PyRayHF (storm-time ray tracer)** — `models/rayhf/rayhf_wrapper.py`
When there's a storm, you can't trust a climatology or an assimilated average — the
project **ray-traces** the signal through an IRI electron-density profile to compute the
virtual height *directly* from the physics of refraction. It:
1. gets an IRI electron-density profile (100–500 km, 10 km steps);
2. gets the magnetic field along that column;
3. builds the plasma-frequency and gyro-frequency ratios the ray tracer needs;
4. calls `find_vh(...)` and takes the **last non-NaN layer** as the reflection point
   (the ray "reflects" before it reaches the density peak, so you can't just take the
   peak height);
5. sanity-checks the result is 50–1000 km.

**Important honesty note:** PyRayHF is a *proxy* for the storm slot. The problem statement
imagined SAMI3 (a first-principles physics model); SAMI3 is **not integrated**. Also,
PyRayHF currently runs at a **fixed internal frequency of 5.0 MHz** regardless of the
request frequency (`_F_MHZ = 5.0`) — a known limitation documented in `docs/known_limitations.md`
(item 3 / "D8").

### 4.3 What comes back

`get_ionosphere` always returns a dict with `model_used` (what actually produced the
answer, after any fallback), `selected_model` (what was attempted — the audit trail),
`reason` (human-readable), and `profile` (the ionospheric parameters). The SSL algorithm
pulls the virtual height out of that profile via `_extract_height`: ray-traced
`virtual_height_km` for PyRayHF, else `hmF2` for everything else.

---

## 5. The GP correction layer (the "machine learning" part)

### 5.1 What it is and why

Even with a good ionospheric model, the SSL physics estimate is *systematically* off —
the model's virtual height doesn't perfectly match reality, so the projected location has a
repeatable bias. A **Gaussian Process (GP)** regressor learns that bias from data and
predicts a correction, plus an uncertainty bar. GPs are a good fit here because they give
calibrated uncertainty and work well on modest datasets.

### 5.2 How it's structured (`models/ssl_gp_model.py`)

- **Two separate populations, trained independently**: one GP pair for **IRTAM** (nominal)
  rows, one GP pair for **PyRayHF/storm** rows. (Each "pair" = one GP for the latitude
  residual + one for the longitude residual.) They're trained separately because storm and
  nominal errors have structurally different shapes — mixing them collapses the kernel.
- **Kernel**: `RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)` — the RBF captures
  smooth structure, the WhiteKernel captures irreducible noise. `normalize_y=True`,
  `n_restarts_optimizer=3`.
- **Features fed to the GP** (order matters, must match training exactly):
  `[azimuth, elevation, frequency_mhz, virtual_height_km, kp, dst, hour, month,
  baseline_lat, baseline_lon]`.
- **Targets**: `residual_lat` and `residual_lon` (true minus physics-estimated).
- Trained models are saved as `.pkl` files in `models/saved/`
  (`gp_lat_irtam.pkl`, `gp_lon_irtam.pkl`, `gp_lat_sami3.pkl`, `gp_lon_sami3.pkl` — the
  `sami3` filenames are legacy names for the PyRayHF/storm population).

### 5.3 Out-of-distribution (OOD) guard

The GP was trained on a narrow slice of reality (see §6). If a request comes in for a month
outside {June, July, December} or a latitude outside ~15–35°N, the API sets
`ood_warning: true` — a flag that the correction is being applied outside where it was
learned and should be trusted less.

---

## 6. How the training data was actually made (read this carefully)

This is the part most worth re-understanding, because it's what the accuracy numbers really
mean. The pipeline is `data/generate_real_residuals.py`, fed by real ionosonde + space
weather data.

1. **Start from real measurements**: the merged dataset (`ah223_merged_2012_2013.csv`) has
   ~9.5k rows, each a real timestamp from the **AH223 Ahmedabad ionosonde** in 2012, with a
   real **measured `hmF2`** (peak height) and real space-weather indices (`kp`, `dst`,
   `f107`) merged in from NASA OMNIWeb.
2. **Invent a transmitter** for each row (reproducible, seed 42): pick a random azimuth
   (0–360°), a random ground distance (200–2000 km), and a random frequency. Project from
   the receiver along that azimuth/distance to get a **known "true" transmitter location**.
3. **Synthesize the observation** the receiver would see: the true elevation is computed
   from the *real measured* height, `elevation = arctan(h_measured / distance)`.
4. **Run the actual SSL algorithm** on that observation — but `ssl_locate` uses the
   **modelled** ionosphere (IRTAM/IRI), not the real measured height.
5. **The residual** = (known true location) − (SSL estimate). Because the truth used the
   *measured* height and the estimate used the *modelled* height, **the residual captures
   the ionospheric model's error**, under noise-free geometry.

So the GP is learning: *"given these conditions, how much does the model's virtual height
mislead the SSL fix, and which way?"* — and correcting it. That's a legitimate and useful
thing to learn.

**Two honesty caveats baked into this design** (both documented in `docs/known_limitations.md`):
- The angles of arrival are **noise-free** — no bearing measurement error is injected. Real
  DF stations have azimuth/elevation errors of *degrees*, and elevation error dominates
  range error. This is the single biggest gap between these numbers and operational reality.
  *(This is exactly what the in-progress bearing-noise study — see §11 — is built to measure.)*
- The train/test split is **random at the row level, not blocked by day**. Ionospheric
  residuals are correlated hour-to-hour, so train and test rows from the same day share
  information, which makes the reported improvement optimistic.

---

## 7. What the results actually say

Reproduce them anytime (no retraining, ~1 minute): `python report_table3.py`. I ran it;
it matches the documentation exactly.

| Population | Rows | Test fold | Baseline MAE (physics only) | GP-corrected MAE | Improvement |
|---|---|---|---|---|---|
| **IRTAM** (nominal, 97.6% of data) | 9,228 | 1,846 | 103.29 km | 77.15 km | 26.14 km (25.3%) |
| **PyRayHF** (storm, 2.4% of data) | 229 | 46 | 610.80 km | 111.96 km | 498.84 km (81.7%) |

Error distribution (held-out test folds):

| Statistic | IRTAM baseline | IRTAM corrected | Storm baseline | Storm corrected |
|---|---|---|---|---|
| Median | 62.20 km | 52.23 km | 560.40 km | 95.76 km |
| P90 | 249.55 km | 170.36 km | 1,123.08 km | 243.89 km |
| Worst case | 1,012.35 km | 681.78 km | 1,266.01 km | 314.54 km |

**How to read these honestly:**
- These are **interpolation within the training distribution** — one station, three months
  of 2012 (Solar Cycle 24 peak), simulated emitter geometry, noise-free bearings. They are
  **not** demonstrated generalisation to new stations, dates, or real emitters.
- The GP genuinely reduces error (~25% nominal, ~82% storm), and the physics baseline is a
  real, honest ~103 km under nominal conditions.
- The storm numbers rest on only **46 test rows** — treat them as indicative, not solid.
- `docs/results.md` even keeps a "Numbers never to cite" list of earlier invalid figures —
  a good sign of the project's own discipline.

---

## 8. Repository map (what every important file is)

```
Real-Time-Ionospheric-Geolocation/
├── api/
│   ├── main.py                 # FastAPI service: /locate, /health, / (the map UI)
│   └── static/index.html       # Dark "ops console" Leaflet map front-end
├── models/
│   ├── hybrid_model.py         # get_ionosphere() — routes + runs the chosen model, handles fallback
│   ├── hybrid_selector.py      # select_model() — the storm/latitude/IRTAM/IRI decision rules
│   ├── ssl_algorithm.py        # ssl_locate() — the two-pass SSL geometry (the core deliverable)
│   ├── ssl_gp_model.py         # train_gp() — trains the per-population GP correction pairs
│   ├── iri/iri_wrapper.py      # IRI-2016 climatology wrapper
│   ├── irtam/irtam_wrapper.py  # PyIRTAM real-time assimilated wrapper (local cache)
│   ├── achaim/achaim_wrapper.py# A-CHAIM high-latitude executable wrapper
│   ├── rayhf/rayhf_wrapper.py  # PyRayHF storm-time ray tracer wrapper
│   └── saved/                  # Trained GP .pkl files
├── data/
│   ├── fetch_omni.py           # Pull space-weather indices (kp/dst/f107) from NASA OMNIWeb
│   ├── merge_indices.py        # Merge OMNI indices onto the AH223 ionosonde rows
│   ├── generate_real_residuals.py # Build the residual training set (§6) — the ~125 min run
│   ├── simulate_ssl_dataset.py # Forward grid of SSL outputs (a demo/sanity dataset)
│   ├── time_probe*.py          # Rough per-call timing probes
│   └── processed/              # Datasets (large ones gitignored)
├── report_table3.py            # Reproduce Tables 2–3 from saved models (no retraining)
├── build_report.py             # Builds the DRDO technical report document
├── tests/test_ssl.py           # Regression tests for the API/routing/guards (5 tests)
├── docs/
│   ├── results.md              # Validated results + "numbers never to cite"
│   ├── known_limitations.md    # The honest limitations list (9 items)
│   ├── architecture.md, api_reference.md, deployment.md
│   └── superpowers/specs/      # Design specs (incl. the in-progress test-signal-generator spec)
├── README.md                   # Top-level project readme
├── DRDO_DIA-CoE_EW02_Technical_Report.docx  # The technical report deliverable
└── DRDO_DIA_CoE_EW_02_brief.md # The official problem statement + a (stale) status note
```

---

## 9. How to run everything

All commands from the repo root, using the project's Python
(`C:\Users\prith\anaconda3\python.exe`).

**Run the API + map UI:**
```powershell
& "C:\Users\prith\anaconda3\python.exe" -m uvicorn api.main:app --reload
# then open http://127.0.0.1:8000
```

**Send a test query:**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/locate" -ContentType "application/json" -Body '{"receiver_lat":23.0,"receiver_lon":72.0,"azimuth_deg":45.0,"elevation_deg":30.0,"frequency_mhz":10.0,"timestamp":"2012-06-15T12:00:00","kp":2.0,"dst":-20.0,"irtam_available":true}'
```

**Reproduce the headline results (~1 min, no retraining):**
```powershell
& "C:\Users\prith\anaconda3\python.exe" report_table3.py
```

**Run the tests:**
```powershell
& "C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_ssl.py -v
```

**Rebuild the training data from scratch (~125 min):**
```powershell
& "C:\Users\prith\anaconda3\python.exe" data/fetch_omni.py
& "C:\Users\prith\anaconda3\python.exe" data/merge_indices.py
& "C:\Users\prith\anaconda3\python.exe" data/generate_real_residuals.py
# then retrain: python models/ssl_gp_model.py
```

---

## 10. Known limitations (the honest list)

From `docs/known_limitations.md`, in plain terms:
1. **Scope**: one station, three months of 2012, simulated geometry. All numbers are
   within-distribution, not generalisation.
2. **No held-out station** ("Approach B") — the recommended next validation step.
3. **PyRayHF fixed at 5 MHz** while the GP sees the request frequency — an inconsistency
   for the storm population.
4. **F10.7 defaults to 130 SFU** if not supplied — correct for 2012, wrong for other epochs.
5. **A-CHAIM never fires** at India geometry — untested in the demo environment.
6. **Storm GP trained on 183 rows** — small; high variance.
7. **Two-call model inconsistency** at the 60° latitude boundary (never fires at 23°N).
8. **Antimeridian midpoint arithmetic** — simple longitude averaging breaks near ±180°
   (never fires in India).
9. **No inter-annual validation** — only 2012 data.

Plus the two structural caveats from §6: **noise-free bearings** and **row-level split**.

---

## 11. What's in progress right now

Two new pieces are specced (see
`docs/superpowers/specs/2026-07-01-test-signal-generator-and-bearing-noise-study-design.md`)
and about to be built — they close the two biggest deliverable gaps:

1. **Test signal generation tool** (`data/generate_test_signals.py`) — an explicit DRDO
   deliverable. It places emitters at *known* lat/lon, synthesises the exact az/el/freq a
   receiver would observe (forward geometry through the real ionosphere), and writes them
   out as ground-truth "test signals." This lets the Figure of Merit be measured against a
   known answer, not just ionospheric MAE.
2. **Bearing-noise sensitivity study** (`bearing_noise_study.py`) — injects realistic
   Gaussian error into the azimuth and elevation (swept independently on a 2D grid), runs
   the real `ssl_locate`, and reports how accuracy degrades. This directly answers the first
   question a DF/EW reviewer will ask: *"what happens when the bearings aren't perfect?"* —
   which the current numbers don't address.

---

## 12. Glossary (quick reference)

| Term | Meaning |
|---|---|
| **HF** | High Frequency, 3–30 MHz (shortwave). Propagates far via skywave. |
| **Skywave** | Signal path that refracts off the ionosphere back to Earth. |
| **SSL** | Single Station Location — getting a full position fix from one DF station. |
| **DF** | Direction Finding — measuring a signal's angle of arrival. |
| **Azimuth** | Compass bearing of the incoming signal (0–360°). |
| **Elevation** | Angle of the incoming signal above the horizon. |
| **Ionosphere** | Ionised upper-atmosphere layer (~100–500 km) that refracts HF. |
| **Virtual height** | Equivalent "mirror" height for the ionospheric bounce; drives the SSL triangle. |
| **hmF2** | True height of the ionosphere's F2-layer peak density (km). |
| **NmF2** | Peak electron density of the F2 layer (m⁻³). |
| **foF2** | F2-layer critical frequency (MHz) — the highest frequency reflected straight up. |
| **MUF** | Maximum Usable Frequency — above it, the signal penetrates instead of reflecting. |
| **TEC** | Total Electron Content along a path (TECU). |
| **Kp** | Planetary geomagnetic activity index, 0 (calm) – 9 (extreme storm). |
| **Dst** | Storm-time ring-current index (nT); strongly negative = storm. |
| **F10.7** | Solar radio flux at 10.7 cm (SFU) — a proxy for solar activity level. |
| **IRI** | International Reference Ionosphere — the standard climatological model. |
| **IRTAM** | IRI Real-Time Assimilative Model — IRI corrected with live ionosonde data. |
| **A-CHAIM** | Canadian high-latitude/Arctic ionospheric model. |
| **PyRayHF** | HF ray-tracing library used here as the storm-time virtual-height source. |
| **GP** | Gaussian Process — the ML regressor learning the residual correction + uncertainty. |
| **Ionosonde** | Ground instrument that sounds the ionosphere and measures hmF2/foF2 etc. |
| **GIRO** | Global Ionosphere Radio Observatory — source of the ionosonde/IRTAM coefficients. |
| **OMNIWeb** | NASA service providing space-weather indices (Kp, Dst, F10.7). |
| **AH223** | The Ahmedabad ionosonde station (23°N, 72.6°E) the training data comes from. |
| **MAE** | Mean Absolute Error — the accuracy metric (km, great-circle). |
| **OOD** | Out Of Distribution — an input outside where the GP was trained. |

---

*This walkthrough describes the codebase as of 2026-07-01. If you change the physics,
the models, or the data pipeline, update §2–§6 to match.*
