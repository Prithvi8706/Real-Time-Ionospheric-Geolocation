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
