"""
Bearing-noise sensitivity study — DRDO DIA-CoE/EW/02 Figure of Merit.

Injects independent zero-mean Gaussian error into the azimuth and elevation
of the ground-truth test signals (data/processed/test_signals.csv), runs the
real ssl_locate, and reports how geolocation accuracy degrades. The
(az_sigma=0, el_sigma=0) cell is the algorithm's intrinsic error floor.

Design: docs/superpowers/specs/2026-07-01-test-signal-generator-and-bearing-noise-study-design.md §3.2

Run from repo root (anaconda python — the env with a working IRI backend):
    python bearing_noise_study.py
Writes:
    data/processed/bearing_noise_results.csv
"""

import os
import time
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd

import models.ssl_algorithm as ssl_mod
from models.ssl_algorithm import ssl_locate, compute_transmitter_location
from data.generate_test_signals import (
    build_test_signal_set,
    haversine_km,
    OUTPUT_CSV as SIGNALS_CSV,
)

AZ_SIGMAS = [0.0, 0.5, 1.0, 2.0]
EL_SIGMAS = [0.0, 0.5, 1.0, 2.0]
SEED = 42
QUANT_DEG = 0.1  # well below the ionosphere's native spatial resolution
EL_MIN_DEG, EL_MAX_DEG = 1.0, 60.0
CALL_BUDGET_S = 240.0  # keep the full run under ~5 min (spec §3.2)
N_CANDIDATES = [40, 30, 20, 10, 5, 3, 2, 1]

RESULTS_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "processed", "bearing_noise_results.csv",
)


def make_memoized(fn, quant_deg: float = QUANT_DEG):
    """
    Memoize an ionosphere lookup on coordinates quantized to `quant_deg`
    cells (plus the exact conditions). 0.1 deg (~11 km) is well below the
    ionosphere's native spatial resolution, so cache hits are physically
    negligible while collapsing thousands of model calls.
    """
    cache = {}
    stats = {"calls": 0, "misses": 0}

    def wrapper(lat, lon, dt, kp, dst, irtam_available=False):
        stats["calls"] += 1
        key = (round(lat / quant_deg), round(lon / quant_deg),
               dt, kp, dst, irtam_available)
        if key not in cache:
            stats["misses"] += 1
            cache[key] = fn(lat=lat, lon=lon, dt=dt, kp=kp, dst=dst,
                            irtam_available=irtam_available)
        return cache[key]

    wrapper.stats = stats
    return wrapper


@contextmanager
def memoized_ionosphere(quant_deg: float = QUANT_DEG):
    """Patch models.ssl_algorithm.get_ionosphere with a memoizing wrapper
    for the duration of the study only. Production code untouched."""
    original = ssl_mod.get_ionosphere
    wrapper = make_memoized(original, quant_deg)
    ssl_mod.get_ionosphere = wrapper
    try:
        yield wrapper
    finally:
        ssl_mod.get_ionosphere = original


def run_trials(
    signals: pd.DataFrame,
    az_sigmas=AZ_SIGMAS,
    el_sigmas=EL_SIGMAS,
    n_realizations: int = 20,
    seed: int = SEED,
) -> pd.DataFrame:
    """
    For every (az_sigma, el_sigma) cell and every test signal, draw
    n_realizations Gaussian noise realizations, run the real ssl_locate on
    the noisy bearing, and record the haversine error vs the known emitter.

    Deterministic: fixed seed, fixed loop order (cells -> signals -> trials).
    """
    rng = np.random.default_rng(seed)
    rows = []
    for az_sigma in az_sigmas:
        for el_sigma in el_sigmas:
            for sig in signals.itertuples():
                dt = datetime.fromisoformat(sig.timestamp)
                for k in range(n_realizations):
                    az_noisy = float(
                        (sig.azimuth_deg + az_sigma * rng.standard_normal())
                        % 360.0
                    )
                    el_noisy = float(np.clip(
                        sig.elevation_deg + el_sigma * rng.standard_normal(),
                        EL_MIN_DEG, EL_MAX_DEG,
                    ))
                    result = ssl_locate(
                        sig.receiver_lat, sig.receiver_lon,
                        az_noisy, el_noisy,
                        frequency_mhz=sig.frequency_mhz,
                        dt=dt, kp=sig.kp, dst=sig.dst,
                    )
                    rows.append({
                        "az_sigma":            az_sigma,
                        "el_sigma":            el_sigma,
                        "signal_id":           sig.Index,
                        "realization":         k,
                        "emitter_lat":         sig.emitter_lat,
                        "emitter_lon":         sig.emitter_lon,
                        "azimuth_noisy_deg":   az_noisy,
                        "elevation_noisy_deg": el_noisy,
                        "tx_lat":              result.transmitter_lat,
                        "tx_lon":              result.transmitter_lon,
                        "error_km":            haversine_km(
                            sig.emitter_lat, sig.emitter_lon,
                            result.transmitter_lat, result.transmitter_lon,
                        ),
                        "model_used":          result.model_used,
                        "timestamp":           sig.timestamp,
                        "kp":                  sig.kp,
                        "dst":                 sig.dst,
                    })
    return pd.DataFrame(rows)


def summarize(trials: pd.DataFrame) -> dict:
    """MAE / median / P90 of error_km per (az_sigma, el_sigma) cell."""
    aggs = {
        "MAE": "mean",
        "median": "median",
        "P90": lambda s: s.quantile(0.9),
    }
    return {
        name: trials.pivot_table(
            index="az_sigma", columns="el_sigma",
            values="error_km", aggfunc=fn,
        ).round(1)
        for name, fn in aggs.items()
    }
