"""
Test signal generator — DRDO DIA-CoE/EW/02 deliverable.

Places emitters at KNOWN lat/lon and synthesizes the exact
(azimuth, elevation, frequency) a receiver would observe via forward
geometry through the real hybrid ionosphere. Output signals are
ground truth the SSL solver's accuracy can be measured against.

Design: docs/superpowers/specs/2026-07-01-test-signal-generator-and-bearing-noise-study-design.md

Run from repo root:
    python data/generate_test_signals.py
Writes:
    data/processed/test_signals.csv
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from models.hybrid_model import get_ionosphere
from models.ssl_algorithm import (
    EARTH_RADIUS_KM,
    _extract_height,
    compute_transmitter_location,
)

# AH223 Ahmedabad receiver (spec §3.1)
RECEIVER_LAT = 23.0
RECEIVER_LON = 72.6

# Solver's validated elevation band — signals outside are invalid inputs
ELEVATION_MIN_DEG = 1.0
ELEVATION_MAX_DEG = 60.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle ground range on the same sphere the solver uses."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = phi2 - phi1
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlmb / 2) ** 2
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a)))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing point1 -> point2, normalized to [0, 360)."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dlmb = np.radians(lon2 - lon1)
    y = np.sin(dlmb) * np.cos(phi2)
    x = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlmb)
    return float(np.degrees(np.arctan2(y, x)) % 360.0)


def gc_midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Great-circle midpoint — the skywave bounce point for a single hop."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    lmb1 = np.radians(lon1)
    dlmb = np.radians(lon2 - lon1)
    bx = np.cos(phi2) * np.cos(dlmb)
    by = np.cos(phi2) * np.sin(dlmb)
    mid_lat = np.arctan2(
        np.sin(phi1) + np.sin(phi2),
        np.sqrt((np.cos(phi1) + bx) ** 2 + by ** 2),
    )
    mid_lon = lmb1 + np.arctan2(by, np.cos(phi1) + bx)
    return float(np.degrees(mid_lat)), float(np.degrees(mid_lon))


@dataclass
class ObservationTruth:
    """A ground-truth test signal: known emitter + what the receiver observes."""
    emitter_lat: float
    emitter_lon: float
    receiver_lat: float
    receiver_lon: float
    azimuth_deg: float
    elevation_deg: float
    frequency_mhz: float
    ground_range_km: float
    virtual_height_km: float
    model_used: str
    dt: datetime
    kp: float
    dst: float


def synthesize_observation(
    emitter_lat: float,
    emitter_lon: float,
    receiver_lat: float,
    receiver_lon: float,
    frequency_mhz: float,
    dt: datetime,
    kp: float,
    dst: float,
    irtam_available: bool = False,
) -> ObservationTruth:
    """
    Forward geometry: known emitter -> the (az, el) the receiver observes.

    Exact inverse of the solver: elevation = atan(h / ground_range) inverts
    compute_ground_distance's ground_distance = h / tan(elevation), with h
    taken from the real hybrid ionosphere at the great-circle bounce midpoint
    via the same _extract_height logic ssl_locate uses.
    """
    ground_range_km = haversine_km(receiver_lat, receiver_lon, emitter_lat, emitter_lon)
    azimuth_deg = initial_bearing_deg(receiver_lat, receiver_lon, emitter_lat, emitter_lon)

    mid_lat, mid_lon = gc_midpoint(receiver_lat, receiver_lon, emitter_lat, emitter_lon)
    iono = get_ionosphere(
        lat=mid_lat, lon=mid_lon, dt=dt, kp=kp, dst=dst,
        irtam_available=irtam_available,
    )
    virtual_height_km = _extract_height(iono["profile"])

    elevation_deg = float(np.degrees(np.arctan(virtual_height_km / ground_range_km)))

    return ObservationTruth(
        emitter_lat=emitter_lat,
        emitter_lon=emitter_lon,
        receiver_lat=receiver_lat,
        receiver_lon=receiver_lon,
        azimuth_deg=azimuth_deg,
        elevation_deg=elevation_deg,
        frequency_mhz=frequency_mhz,
        ground_range_km=ground_range_km,
        virtual_height_km=virtual_height_km,
        model_used=iono["model_used"],
        dt=dt,
        kp=kp,
        dst=dst,
    )


# ── Reproducible emitter set (spec §3.1) ─────────────────────────────────

AZIMUTHS_DEG = list(np.arange(0.0, 360.0, 45.0))
GROUND_RANGES_KM = [800.0, 1500.0, 2200.0]
FREQUENCY_MHZ = 10.0
CONDITIONS = [
    {"dt": datetime(2012, 6, 15, 12, 0, 0), "kp": 1.0, "dst": -10.0},
    {"dt": datetime(2012, 6, 15, 0, 0, 0),  "kp": 1.0, "dst": -10.0},
    {"dt": datetime(2012, 6, 15, 12, 0, 0), "kp": 6.0, "dst": -120.0},
]

OUTPUT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "processed", "test_signals.csv",
)


def build_test_signal_set(
    receiver_lat: float = RECEIVER_LAT,
    receiver_lon: float = RECEIVER_LON,
    azimuths_deg=AZIMUTHS_DEG,
    ground_ranges_km=GROUND_RANGES_KM,
    conditions=CONDITIONS,
    frequency_mhz: float = FREQUENCY_MHZ,
) -> pd.DataFrame:
    """
    Sweep the emitter grid, synthesize each observation against the real
    ionosphere, and drop any signal whose true elevation falls outside the
    solver's validated 1-60 degree band (logged count).
    """
    np.random.seed(42)  # reproducibility anchor for the emitter set (spec §3.1)

    rows = []
    dropped = 0
    for cond in conditions:
        for az in azimuths_deg:
            for rng_km in ground_ranges_km:
                em_lat, em_lon = compute_transmitter_location(
                    receiver_lat, receiver_lon, az, rng_km
                )
                obs = synthesize_observation(
                    em_lat, em_lon, receiver_lat, receiver_lon,
                    frequency_mhz=frequency_mhz,
                    dt=cond["dt"], kp=cond["kp"], dst=cond["dst"],
                )
                if not (ELEVATION_MIN_DEG <= obs.elevation_deg <= ELEVATION_MAX_DEG):
                    dropped += 1
                    continue
                rows.append({
                    "emitter_lat":        obs.emitter_lat,
                    "emitter_lon":        obs.emitter_lon,
                    "receiver_lat":       obs.receiver_lat,
                    "receiver_lon":       obs.receiver_lon,
                    "azimuth_deg":        obs.azimuth_deg,
                    "elevation_deg":      obs.elevation_deg,
                    "frequency_mhz":      obs.frequency_mhz,
                    "ground_range_km":    obs.ground_range_km,
                    "virtual_height_km":  obs.virtual_height_km,
                    "model_used":         obs.model_used,
                    "timestamp":          obs.dt.isoformat(),
                    "kp":                 obs.kp,
                    "dst":                obs.dst,
                })

    if dropped:
        print(f"Dropped {dropped} signal(s) with elevation outside "
              f"[{ELEVATION_MIN_DEG}, {ELEVATION_MAX_DEG}] deg")
    return pd.DataFrame(rows, columns=[
        "emitter_lat", "emitter_lon", "receiver_lat", "receiver_lon",
        "azimuth_deg", "elevation_deg", "frequency_mhz",
        "ground_range_km", "virtual_height_km", "model_used",
        "timestamp", "kp", "dst",
    ])


if __name__ == "__main__":
    df = build_test_signal_set()
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(df)} test signals to {OUTPUT_CSV}")
    print(df.head(10).to_string())
