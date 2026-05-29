# Deployment Guide — Real-Time Ionospheric Geolocation

**Problem ID:** DRDO DIA-CoE/EW/02  
**Target platform:** Windows 11, Anaconda Python 3.12

---

## Prerequisites

Install the following before proceeding.

### 1. Python environment

- Anaconda or Miniconda with Python 3.12
- The following packages must be available in the active environment:

```
fastapi
uvicorn[standard]
pydantic
numpy
scikit-learn
joblib
pandas
iri2016
PyIRTAM       (case-sensitive import name)
PyRayHF       (renamed from pyrrayhf; install the DRDO-approved wheel)
```

Install from the project root:

```powershell
pip install -r requirements.txt
```

### 2. PyIRTAM coefficient files

PyIRTAM requires date-specific IRTAM coefficient files on disk. The
wrapper calls `PyIRTAM.lib.run_PyIRTAM(..., download=False)`, meaning it
reads from the local cache and will not attempt an internet download.

Coefficient files must be present for every date in the demo dataset
(June, July, December 2012). If the files are absent for a requested date,
`get_irtam_profile()` returns null fields and the system falls back to IRI.
The `irtam_available` flag in the request should be set to `false` when
files are not present.

### 3. PyRayHF

PyRayHF must be importable as `import PyRayHF.library as rayhf`. Confirm:

```powershell
python -c "import PyRayHF.library; print('OK')"
```

If this fails, install the wheel provided in the project or by DRDO.

### 4. A-CHAIM v6.0.3

A-CHAIM is only invoked for |latitude| ≥ 60°. At the AH223 Ahmedabad
station (23°N) it never fires. For completeness, or if the system is
deployed at a higher-latitude site, the A-CHAIM executable and database
must be present.

**IMPORTANT:** The default fallback paths in `models/hybrid_model.py` are
hardcoded to a development machine path:

```python
ACHAIM_EXE_PATH = os.environ.get(
    "ACHAIM_EXE_PATH",
    "C:/Users/prith/Downloads/A-CHAIM_User_Release-6.0.3/..."
)
```

**This path does not exist on the DRDO lab machine.** You must set the
environment variables before starting the server. Failure to do so will
cause A-CHAIM calls to fail silently (it falls back to IRI), but the
paths will generate a misleading default in logs.

---

## Environment variable setup

Open a PowerShell session before starting the server:

```powershell
$env:ACHAIM_EXE_PATH = "C:\path\to\A-CHAIM_User_Release-6.0.3\C\ACHAIM\ACHAIM.exe"
$env:ACHAIM_DB_PATH  = "C:\path\to\A-CHAIM_User_Release-6.0.3\C\example\example.db"
```

Replace the paths with the actual installation paths on the DRDO machine.

To make these persistent across PowerShell sessions, add them to your
PowerShell profile (`$PROFILE`) or use the Windows System Environment
Variables dialog.

---

## Starting the server

From the project root:

```powershell
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Or use the `__main__` entry point:

```powershell
python api/main.py
```

The service binds to `http://127.0.0.1:8000` by default. The Leaflet
ops-console UI is accessible at that address from any browser on the
same machine.

To bind to the local network (accessible from other machines on the lab
LAN), change `--host` to `0.0.0.0`. Confirm with the network security
officer before doing this in a sensitive environment.

---

## Pre-demo checklist

Run these three checks before any evaluation or demonstration.

### 1. Latency benchmark

Target: each `/locate` call should complete in under 5 seconds on the
demo machine. Run a representative request and observe the response time:

```powershell
Measure-Command {
  Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/locate `
    -ContentType "application/json" `
    -Body '{"receiver_lat":23.0,"receiver_lon":72.0,"azimuth_deg":45.0,
            "elevation_deg":15.0,"frequency_mhz":10.0,
            "timestamp":"2012-06-15T12:00:00",
            "kp":1.0,"dst":-10.0,"f107":130.0,"irtam_available":true}'
}
```

If latency exceeds 5 seconds, the PyIRTAM coefficient lookup or the
scikit-learn GP prediction is slower than expected. Check CPU frequency
scaling settings.

### 2. Health check — verify GP training rows

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json
```

Expected output:

```json
{
  "status": "ok",
  "gp_models_loaded": true,
  "gp_models": { "irtam": true, "sami3": true },
  "gp_training_rows": { "irtam": 7382, "sami3": 183 }
}
```

If `gp_models_loaded` is `false` or training row counts differ, the GP
`.pkl` files in `models/saved/` are missing or corrupt. Retrain with:

```powershell
python models/ssl_gp_model.py
```

This requires the residuals CSV at `data/processed/ssl_real_residuals_2012.csv`.

### 3. Regression test suite

```powershell
python -m pytest tests/test_ssl.py -v
```

Expected output: **5 passed**, 0 failed, 0 errors.

| Test | What it checks |
|---|---|
| `test_sunny_day_irtam_gp` | Nominal IRTAM path: `model_used=IRTAM`, `gp_correction.status=applied` |
| `test_storm_routing_rayhf` | Storm path (Kp=6): `model_used=PyRayHF`, storm GP applied |
| `test_irtam_fallback_to_iri` | D1 fix: fallback audit trail, `model_used=IRI`, `selected_model=IRTAM`, GP `not_applied` |
| `test_elevation_guard` | Input validation: `elevation_deg=0.5` → 422 |
| `test_ood_month_warning` | OOD detection: November timestamp → `ood_warning=true` |

---

## Air-gap operation

**UI shell:** The Leaflet library (CSS + JS) is served from `api/static/`.
The ops-console UI loads without internet access.

**Map tiles:** Live raster tile imagery is fetched from OpenStreetMap at
runtime. In a full air-gap environment this will fail silently (grey map
tiles). Two options for full air-gap:

1. **Pre-cache tiles**: Use a tool such as `tilesaver` to download a
   bounding-box tile set for the region of interest, then serve them from
   a local TileServer GL instance. Update the tile URL in `api/static/index.html`.

2. **Replace tile source**: Substitute the OpenStreetMap tile URL in
   `index.html` with a local GeoTIFF or a pre-rendered static image map.

The geolocation pipeline itself (all Python, model files, and the Leaflet
overlay logic) operates fully offline.

---

## File layout after deployment

```
Real-Time-Ionospheric-Geolocation/
├── api/
│   ├── main.py
│   └── static/
│       ├── index.html
│       ├── leaflet.css
│       └── leaflet.js
├── models/
│   ├── hybrid_model.py
│   ├── hybrid_selector.py
│   ├── ssl_algorithm.py
│   ├── ssl_gp_model.py
│   ├── saved/
│   │   ├── gp_lat_irtam.pkl
│   │   ├── gp_lon_irtam.pkl
│   │   ├── gp_lat_sami3.pkl
│   │   └── gp_lon_sami3.pkl
│   ├── iri/iri_wrapper.py
│   ├── irtam/irtam_wrapper.py
│   ├── achaim/achaim_wrapper.py
│   └── rayhf/rayhf_wrapper.py
├── tests/test_ssl.py
├── data/processed/ssl_real_residuals_2012.csv   ← required for GP retraining
└── docs/
    ├── api_reference.md
    ├── architecture.md
    ├── results.md
    ├── deployment.md
    └── known_limitations.md
```
