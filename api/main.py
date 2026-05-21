"""
Real-Time Ionospheric Geolocation — FastAPI service.
DRDO Problem ID: DIA-CoE/EW/02

Exposes the end-to-end SSL geolocation pipeline over HTTP.
The primary (headline) result is the physics-only SSL estimate.
The GP correction is a secondary, clearly-labelled framework component
trained on synthetic residuals — not a validated operational correction.
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
_GP_LAT_PATH = os.path.join(_ROOT, "models", "saved", "gp_lat.pkl")
_GP_LON_PATH = os.path.join(_ROOT, "models", "saved", "gp_lon.pkl")

# Load GP models once at startup; failures are non-fatal.
_gp_lat = None
_gp_lon = None
_gp_models_loaded = False

try:
    _gp_lat = joblib.load(_GP_LAT_PATH)
    _gp_lon = joblib.load(_GP_LON_PATH)
    _gp_models_loaded = True
except Exception as _e:
    print(f"WARNING: GP model files could not be loaded ({_e}). "
          "GP correction will return null fields.")

# ── Landing page HTML (loaded once at startup) ───────────────────────────
_STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_STATIC_DIR, "static", "index.html"), encoding="utf-8") as _f:
    _PAGE_HTML = _f.read()

# ── FastAPI app ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Real-Time Ionospheric Geolocation",
    description=(
        "Single-station HF emitter geolocation via SSL physics + "
        "hybrid ionospheric model (IRI / PyIRTAM / A-CHAIM). "
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


class LocateResponse(BaseModel):
    primary_estimate: PrimaryEstimate
    ionosphere: IonosphereInfo
    gp_correction: GPCorrection


# ── GP correction helper ─────────────────────────────────────────────────

_GP_NOTE = (
    "GP currently trained on synthetic residuals; not a validated correction. "
    "Pending retraining on real SSL residuals from AH223 data."
)

_GP_NULL = GPCorrection(
    status="framework_component",
    note=_GP_NOTE,
    corrected_lat=None,
    corrected_lon=None,
    uncertainty_lat_deg=None,
    uncertainty_lon_deg=None,
)


def apply_gp_correction(ssl_result: SSLResult, request: LocateRequest) -> GPCorrection:
    """Apply the GP residual correction as a secondary, experimental step."""
    if not _gp_models_loaded or _gp_lat is None or _gp_lon is None:
        return _GP_NULL

    try:
        dt = datetime.fromisoformat(request.timestamp)

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
            ssl_result.transmitter_lat,   # baseline = SSL physics output
            ssl_result.transmitter_lon,
        ]])

        residual_lat, std_lat = _gp_lat.predict(features, return_std=True)
        residual_lon, std_lon = _gp_lon.predict(features, return_std=True)

        corrected_lat = round(float(ssl_result.transmitter_lat + residual_lat[0]), 4)
        corrected_lon = round(float(ssl_result.transmitter_lon + residual_lon[0]), 4)

        return GPCorrection(
            status="framework_component",
            note=_GP_NOTE,
            corrected_lat=corrected_lat,
            corrected_lon=corrected_lon,
            uncertainty_lat_deg=round(float(std_lat[0]), 4),
            uncertainty_lon_deg=round(float(std_lon[0]), 4),
        )

    except Exception as e:
        print(f"WARNING: GP correction failed: {type(e).__name__}: {e}")
        return _GP_NULL


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(content=_PAGE_HTML)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "gp_models_loaded": _gp_models_loaded,
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
