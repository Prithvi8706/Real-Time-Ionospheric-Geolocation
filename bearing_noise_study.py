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

    def wrapper(lat, lon, dt, kp, dst, irtam_available=False, **kwargs):
        stats["calls"] += 1
        key = (round(lat / quant_deg), round(lon / quant_deg),
               dt, kp, dst, irtam_available, tuple(sorted(kwargs.items())))
        if key not in cache:
            stats["misses"] += 1
            cache[key] = fn(lat=lat, lon=lon, dt=dt, kp=kp, dst=dst,
                            irtam_available=irtam_available, **kwargs)
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


def estimate_misses(
    signals: pd.DataFrame,
    n_realizations: int,
    quant_deg: float = QUANT_DEG,
    assumed_height_km: float = 300.0,
) -> int:
    """
    Dry-run the exact trial loop (same seed, same rng consumption order)
    with pure geometry at a fixed virtual height and count the unique
    quantized ionosphere keys ssl_locate would request. Real heights vary
    ~285-315 km so this estimate is close but not exact — callers apply a
    safety margin.
    """
    rng = np.random.default_rng(SEED)
    keys = set()
    for az_sigma in AZ_SIGMAS:
        for el_sigma in EL_SIGMAS:
            for sig in signals.itertuples():
                keys.add((round(sig.receiver_lat / quant_deg),
                          round(sig.receiver_lon / quant_deg),
                          sig.timestamp, sig.kp, sig.dst))
                for _ in range(n_realizations):
                    az_noisy = (sig.azimuth_deg
                                + az_sigma * rng.standard_normal()) % 360.0
                    el_noisy = np.clip(
                        sig.elevation_deg + el_sigma * rng.standard_normal(),
                        EL_MIN_DEG, EL_MAX_DEG,
                    )
                    d_rough = assumed_height_km / np.tan(np.radians(el_noisy))
                    tx_lat, tx_lon = compute_transmitter_location(
                        sig.receiver_lat, sig.receiver_lon, az_noisy, d_rough
                    )
                    mid_lat = (sig.receiver_lat + tx_lat) / 2
                    mid_lon = (sig.receiver_lon + tx_lon) / 2
                    keys.add((round(mid_lat / quant_deg),
                              round(mid_lon / quant_deg),
                              sig.timestamp, sig.kp, sig.dst))
    return len(keys)


def choose_n_realizations(latency_s: float, signals: pd.DataFrame):
    """Largest candidate N whose estimated model-call time fits the budget."""
    est_s = None
    for n in N_CANDIDATES:
        est_s = estimate_misses(signals, n) * 1.2 * latency_s
        if est_s <= CALL_BUDGET_S:
            return n, est_s
    return 1, est_s


def _probe_latency_s(n_probe: int = 3) -> float:
    """Median wall time of a real, uncached ionosphere call."""
    from models.hybrid_model import get_ionosphere as real_get_ionosphere
    dt = datetime(2012, 6, 15, 12, 0, 0)
    times = []
    for i in range(n_probe):
        t0 = time.perf_counter()
        real_get_ionosphere(lat=10.0 + 0.37 * i, lon=65.0, dt=dt,
                            kp=1.0, dst=-10.0, irtam_available=False)
        times.append(time.perf_counter() - t0)
    return float(np.median(times))


def main() -> None:
    if os.path.exists(SIGNALS_CSV):
        signals = pd.read_csv(SIGNALS_CSV)
    else:
        print(f"{SIGNALS_CSV} not found — generating it first")
        signals = build_test_signal_set()
        os.makedirs(os.path.dirname(SIGNALS_CSV), exist_ok=True)
        signals.to_csv(SIGNALS_CSV, index=False)
    print(f"Loaded {len(signals)} test signals")

    latency_s = _probe_latency_s()
    n, est_s = choose_n_realizations(latency_s, signals)
    print(f"Per-call latency ~{latency_s:.2f}s -> N={n} realizations/cell "
          f"(estimated model-call time ~{est_s:.0f}s)")

    t0 = time.perf_counter()
    with memoized_ionosphere() as iono:
        trials = run_trials(signals, n_realizations=n)
    elapsed = time.perf_counter() - t0
    print(f"Ran {len(trials)} trials in {elapsed:.0f}s "
          f"({iono.stats['calls']} iono calls, {iono.stats['misses']} real)")

    trials.to_csv(RESULTS_CSV, index=False)
    print(f"Saved per-trial results to {RESULTS_CSV}")

    for name, table in summarize(trials).items():
        print(f"\n{name} error (km) — az_sigma rows x el_sigma cols:")
        print(table.to_string())


if __name__ == "__main__":
    main()
