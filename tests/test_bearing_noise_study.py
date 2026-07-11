"""
Unit tests for the bearing-noise sensitivity study.

All ionosphere access is mocked — these tests exercise the study harness
(memoization, noise injection, determinism), not the real models.

Run with:
    python -m pytest tests/test_bearing_noise_study.py -v
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import models.ssl_algorithm as ssl_mod
from bearing_noise_study import make_memoized, memoized_ionosphere

DT = datetime(2012, 6, 15, 12, 0, 0)


def _iono(height_km: float) -> dict:
    return {
        "model_used": "IRTAM",
        "selected_model": "IRTAM",
        "reason": "test fixture",
        "profile": SimpleNamespace(
            hmF2=height_km, virtual_height_km=None, foF2=8.0
        ),
    }


# ── Memoizer ─────────────────────────────────────────────────────────────

def test_memoize_collapses_same_quantized_cell():
    """Coords within the same 0.1-degree cell hit the cache; a new cell,
    or same coords under different conditions, miss."""
    calls = []

    def fake(lat, lon, dt, kp, dst, irtam_available=False):
        calls.append((lat, lon))
        return _iono(300.0)

    wrapped = make_memoized(fake, quant_deg=0.1)

    wrapped(lat=23.001, lon=72.601, dt=DT, kp=1.0, dst=-10.0)
    wrapped(lat=23.049, lon=72.649, dt=DT, kp=1.0, dst=-10.0)  # same cell
    assert len(calls) == 1

    wrapped(lat=23.16, lon=72.601, dt=DT, kp=1.0, dst=-10.0)   # new lat cell
    assert len(calls) == 2

    wrapped(lat=23.001, lon=72.601, dt=DT, kp=6.0, dst=-120.0)  # new conditions
    assert len(calls) == 3

    assert wrapped.stats == {"calls": 4, "misses": 3}


def test_memoized_ionosphere_patches_and_restores():
    """Inside the context ssl_locate resolves to the wrapper; after exit
    (including via exception) the original binding is restored."""
    original = ssl_mod.get_ionosphere

    with memoized_ionosphere() as wrapper:
        assert ssl_mod.get_ionosphere is wrapper
    assert ssl_mod.get_ionosphere is original

    with pytest.raises(RuntimeError):
        with memoized_ionosphere():
            raise RuntimeError("boom")
    assert ssl_mod.get_ionosphere is original


# ── Trial runner ─────────────────────────────────────────────────────────

def _mini_signal_set():
    """4 clean signals from the real generator, constant-height ionosphere."""
    from data.generate_test_signals import build_test_signal_set

    with patch("data.generate_test_signals.get_ionosphere",
               return_value=_iono(300.0)):
        return build_test_signal_set(
            azimuths_deg=[45.0, 200.0],
            ground_ranges_km=[800.0, 1500.0],
            conditions=[{"dt": DT, "kp": 1.0, "dst": -10.0}],
        )


def test_zero_noise_cell_is_intrinsic_floor():
    """With no noise and a constant-height ionosphere, every trial recovers
    the emitter to within coordinate-rounding error (<1 km)."""
    from bearing_noise_study import run_trials

    signals = _mini_signal_set()
    with patch("models.ssl_algorithm.get_ionosphere",
               return_value=_iono(300.0)):
        trials = run_trials(signals, az_sigmas=[0.0], el_sigmas=[0.0],
                            n_realizations=2)

    assert len(trials) == 8  # 4 signals x 1 cell x 2 realizations
    assert (trials["error_km"] < 1.0).all()


def test_noise_is_clipped_and_degrades_accuracy():
    """Elevation noise stays inside [1, 60] deg, and a noisy cell has a
    strictly worse MAE than the zero-noise cell."""
    from bearing_noise_study import run_trials, summarize

    signals = _mini_signal_set()
    with patch("models.ssl_algorithm.get_ionosphere",
               return_value=_iono(300.0)):
        trials = run_trials(signals, az_sigmas=[0.0], el_sigmas=[0.0, 2.0],
                            n_realizations=10)

    assert trials["elevation_noisy_deg"].between(1.0, 60.0).all()

    mae = summarize(trials)["MAE"]
    assert mae.loc[0.0, 2.0] > mae.loc[0.0, 0.0]


def test_run_trials_is_deterministic():
    from bearing_noise_study import run_trials

    signals = _mini_signal_set()
    with patch("models.ssl_algorithm.get_ionosphere",
               return_value=_iono(300.0)):
        a = run_trials(signals, az_sigmas=[1.0], el_sigmas=[1.0],
                       n_realizations=3)
        b = run_trials(signals, az_sigmas=[1.0], el_sigmas=[1.0],
                       n_realizations=3)

    pd.testing.assert_frame_equal(a, b)


# ── Sizing ───────────────────────────────────────────────────────────────

def test_choose_n_scales_with_latency():
    """Fast model -> largest N; very slow model -> smallest N."""
    from bearing_noise_study import choose_n_realizations, N_CANDIDATES

    signals = _mini_signal_set()

    n_fast, _ = choose_n_realizations(latency_s=0.0001, signals=signals)
    assert n_fast == N_CANDIDATES[0]

    n_slow, _ = choose_n_realizations(latency_s=1000.0, signals=signals)
    assert n_slow == 1
