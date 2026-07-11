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
