"""
Real-Time Ionospheric Geolocation — FastAPI service.
DRDO Problem ID: DIA-CoE/EW/02

Exposes the end-to-end SSL geolocation pipeline over HTTP.
The primary (headline) result is the physics-only SSL estimate.
The GP correction is a secondary, clearly-labelled framework component
trained on real AH223 residuals — per-population (IRTAM / PyRayHF).
"""

import warnings
import os
from datetime import datetime
from typing import Optional

import numpy as np

# Suppress harmless pandas numexpr/bottleneck warnings from transitive imports
warnings.filterwarnings("ignore", message=".*numexpr.*")
warnings.filterwarnings("ignore", message=".*bottleneck.*")

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from models.ssl_algorithm import ssl_locate, SSLResult

# ── GP model paths ───────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SAVED = os.path.join(_ROOT, "models", "saved")

# Per-population GP models (Issue 1 fix)
_gp_lat_irtam = None
_gp_lon_irtam = None
_gp_lat_sami3 = None
_gp_lon_sami3 = None
_gp_models_loaded = False

try:
    _gp_lat_irtam = joblib.load(os.path.join(_SAVED, "gp_lat_irtam.pkl"))
    _gp_lon_irtam = joblib.load(os.path.join(_SAVED, "gp_lon_irtam.pkl"))
    _gp_lat_sami3 = joblib.load(os.path.join(_SAVED, "gp_lat_sami3.pkl"))
    _gp_lon_sami3 = joblib.load(os.path.join(_SAVED, "gp_lon_sami3.pkl"))
    _gp_models_loaded = True
except Exception as _e:
    print(f"WARNING: GP model files could not be loaded ({_e}). "
          "GP correction will return null fields.")

# ── Training distribution bounds (for OOD detection) ────────────────────
# Trained on AH223 (23°N), June/July/December 2012, simulated emitter geometry
_OOD_MONTHS = {6, 7, 12}
_OOD_LAT_MIN = 15.0
_OOD_LAT_MAX = 35.0

# ── Landing page HTML (loaded once at startup) ───────────────────────────
_STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_STATIC_DIR, "static", "index.html"), encoding="utf-8") as _f:
    _PAGE_HTML = _f.read()

# ── FastAPI app ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Real-Time Ionospheric Geolocation",
    description=(
        "Single-station HF emitter geolocation via SSL physics + "
        "hybrid ionospheric model (IRI / PyIRTAM / A-CHAIM / PyRayHF storm-time ray tracer). "
        "DRDO DIA-CoE/EW/02"
    ),
    version="1.0.0",
)


# ── Request / response schemas ───────────────────────────────────────────

class LocateRequest(BaseModel):
    receiver_lat: float
    receiver_lon: float
    azimuth_deg: float
    elevation_deg: float
    frequency_mhz: float
    timestamp: str          # ISO 8601, e.g. "2012-06-15T12:00:00"
    kp: float
    dst: float
    irtam_available: bool = False

    @field_validator("timestamp")
    @classmethod
    def _parse_timestamp(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(
                f"Cannot parse '{v}' as ISO 8601 datetime "
                "(expected e.g. '2012-06-15T12:00:00')"
            )
        return v

    @field_validator("elevation_deg")
    @classmethod
    def _validate_elevation(cls, v: float) -> float:
        # Issue 2 fix: tan(0) = division by zero; negative = physically impossible
        if v < 1.0 or v > 60.0:
            raise ValueError(
                f"elevation_deg must be between 1.0 and 60.0 degrees (got {v}). "
                "Values below 1° risk tan(elevation) singularity; "
                "values above 60° are outside typical HF skywave geometry."
            )
        return v

    @field_validator("receiver_lat")
    @classmethod
    def _validate_receiver_lat(cls, v: float) -> float:
        if v < -90.0 or v > 90.0:
            raise ValueError(f"receiver_lat must be between -90 and 90 (got {v})")
        return v

    @field_validator("receiver_lon")
    @classmethod
    def _validate_receiver_lon(cls, v: float) -> float:
        if v < -180.0 or v > 180.0:
            raise ValueError(f"receiver_lon must be between -180 and 180 (got {v})")
        return v

    @field_validator("azimuth_deg")
    @classmethod
    def _validate_azimuth(cls, v: float) -> float:
        if v < 0.0 or v > 360.0:
            raise ValueError(f"azimuth_deg must be between 0 and 360 (got {v})")
        return v

    @field_validator("frequency_mhz")
    @classmethod
    def _validate_frequency(cls, v: float) -> float:
        if v < 2.0 or v > 30.0:
            raise ValueError(
                f"frequency_mhz must be in HF band 2–30 MHz (got {v})"
            )
        return v

    @field_validator("kp")
    @classmethod
    def _validate_kp(cls, v: float) -> float:
        if v < 0.0 or v > 9.0:
            raise ValueError(f"kp must be between 0 and 9 (got {v})")
        return v

    @field_validator("dst")
    @classmethod
    def _validate_dst(cls, v: float) -> float:
        if v < -500.0 or v > 50.0:
            raise ValueError(f"dst must be between -500 and 50 nT (got {v})")
        return v


class PrimaryEstimate(BaseModel):
    transmitter_lat: float
    transmitter_lon: float
    ground_distance_km: float
    virtual_height_km: float
    method: str = "SSL physics (hybrid ionospheric model)"


class IonosphereInfo(BaseModel):
    model_used: str
    reason: str


class GPCorrection(BaseModel):
    status: str
    note: str
    corrected_lat: Optional[float]
    corrected_lon: Optional[float]
    uncertainty_lat_deg: Optional[float]
    uncertainty_lon_deg: Optional[float]
    ood_warning: bool = False                    # Issue 6: OOD detection
    correction_std_km: Optional[float] = None   # Issue 6: uncertainty in km


class LocateResponse(BaseModel):
    primary_estimate: PrimaryEstimate
    ionosphere: IonosphereInfo
    gp_correction: GPCorrection


# ── GP correction helper ─────────────────────────────────────────────────

_GP_NOTE_IRTAM = (
    "GP correction applied (IRTAM population). "
    "Trained on AH223 Ahmedabad data, Jun/Jul/Dec 2012, single-hop simulated geometry. "
    "Do not apply outside this distribution without caution."
)

_GP_NOTE_SAMI3 = (
    "GP correction applied (PyRayHF storm-time population, 229 rows). "
    "Trained on AH223 Ahmedabad data, Jun/Jul/Dec 2012, single-hop simulated geometry. "
    "Small training population — high uncertainty outside training distribution."
)

_GP_NOTE_NO_MODEL = (
    "No per-population GP available for this model branch (IRI or A-CHAIM). "
    "GP correction not applied."
)

_GP_NULL_NO_MODELS = GPCorrection(
    status="unavailable",
    note="GP model files could not be loaded at startup. GP correction disabled.",
    corrected_lat=None,
    corrected_lon=None,
    uncertainty_lat_deg=None,
    uncertainty_lon_deg=None,
    ood_warning=False,
    correction_std_km=None,
)


def _is_ood(request: LocateRequest, dt: datetime) -> bool:
    """Return True if the request is outside the GP training distribution."""
    month_ood = dt.month not in _OOD_MONTHS
    lat_ood = (request.receiver_lat < _OOD_LAT_MIN or
               request.receiver_lat > _OOD_LAT_MAX)
    return month_ood or lat_ood


def apply_gp_correction(ssl_result: SSLResult, request: LocateRequest) -> GPCorrection:
    """Apply the GP residual correction — routes by model_used (Issue 1 fix)."""
    if not _gp_models_loaded:
        return _GP_NULL_NO_MODELS

    # Issue 1 fix: route to correct per-population GP pair
    model = ssl_result.model_used
    if model == "IRTAM":
        gp_lat, gp_lon = _gp_lat_irtam, _gp_lon_irtam
        note = _GP_NOTE_IRTAM
    elif model in ("SAMI3", "PyRayHF"):
        gp_lat, gp_lon = _gp_lat_sami3, _gp_lon_sami3
        note = _GP_NOTE_SAMI3
    else:
        # IRI or A-CHAIM — no GP for these branches
        return GPCorrection(
            status="not_applied",
            note=_GP_NOTE_NO_MODEL,
            corrected_lat=None,
            corrected_lon=None,
            uncertainty_lat_deg=None,
            uncertainty_lon_deg=None,
            ood_warning=False,
            correction_std_km=None,
        )

    try:
        dt = datetime.fromisoformat(request.timestamp)
        ood = _is_ood(request, dt)

        # Feature vector — order must match training exactly:
        # [azimuth, elevation, frequency_mhz, virtual_height_km,
        #  kp, dst, hour, month, baseline_lat, baseline_lon]
        features = np.array([[
            request.azimuth_deg,
            request.elevation_deg,
            request.frequency_mhz,
            ssl_result.virtual_height_km,
            request.kp,
            request.dst,
            dt.hour,
            dt.month,
            ssl_result.transmitter_lat,
            ssl_result.transmitter_lon,
        ]])

        residual_lat, std_lat = gp_lat.predict(features, return_std=True)
        residual_lon, std_lon = gp_lon.predict(features, return_std=True)

        corrected_lat = round(float(ssl_result.transmitter_lat + residual_lat[0]), 4)
        corrected_lon = round(float(ssl_result.transmitter_lon + residual_lon[0]), 4)

        # Approximate correction magnitude in km using std of lat residual
        correction_std_km = round(float(std_lat[0]) * 111.0, 2)

        if ood:
            note += (
                " WARNING: Input is outside GP training distribution "
                "(month or latitude). Correction reliability is reduced."
            )

        return GPCorrection(
            status="applied",
            note=note,
            corrected_lat=corrected_lat,
            corrected_lon=corrected_lon,
            uncertainty_lat_deg=round(float(std_lat[0]), 4),
            uncertainty_lon_deg=round(float(std_lon[0]), 4),
            ood_warning=ood,
            correction_std_km=correction_std_km,
        )

    except Exception as e:
        print(f"WARNING: GP correction failed: {type(e).__name__}: {e}")
        return _GP_NULL_NO_MODELS


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(content=_PAGE_HTML)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "gp_models_loaded": _gp_models_loaded,
        "gp_models": {
            "irtam": _gp_lat_irtam is not None and _gp_lon_irtam is not None,
            "sami3": _gp_lat_sami3 is not None and _gp_lon_sami3 is not None,
        }
    }


@app.post("/locate", response_model=LocateResponse)
def locate(request: LocateRequest):
    dt = datetime.fromisoformat(request.timestamp)

    ssl_result: SSLResult = ssl_locate(
        receiver_lat=request.receiver_lat,
        receiver_lon=request.receiver_lon,
        azimuth_deg=request.azimuth_deg,
        elevation_deg=request.elevation_deg,
        frequency_mhz=request.frequency_mhz,
        dt=dt,
        kp=request.kp,
        dst=request.dst,
        irtam_available=request.irtam_available,
    )

    gp = apply_gp_correction(ssl_result, request)

    return LocateResponse(
        primary_estimate=PrimaryEstimate(
            transmitter_lat=ssl_result.transmitter_lat,
            transmitter_lon=ssl_result.transmitter_lon,
            ground_distance_km=ssl_result.ground_distance_km,
            virtual_height_km=ssl_result.virtual_height_km,
        ),
        ionosphere=IonosphereInfo(
            model_used=ssl_result.model_used,
            reason=ssl_result.reason,
        ),
        gp_correction=gp,
    )


# ── Dev entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)