# Bearing-Noise Sensitivity Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `bearing_noise_study.py` — the Figure-of-Merit study that injects Gaussian azimuth/elevation error into the ground-truth test signals and measures how `ssl_locate` accuracy degrades — plus `docs/bearing_noise_results.md`, per §3.2/§3.3 of `docs/superpowers/specs/2026-07-01-test-signal-generator-and-bearing-noise-study-design.md`.

**Architecture:** A repo-root script (convention: next to `report_table3.py`) with four separable pieces: (1) a memoizing wrapper monkeypatched over `models.ssl_algorithm.get_ionosphere` for the duration of the run only (context manager, keyed on coordinates quantized to 0.1°); (2) `run_trials()` — the 4×4 sigma grid × signals × N noise realizations loop through the real `ssl_locate`, returning a per-trial DataFrame; (3) `summarize()` — MAE/median/P90 pivot tables; (4) a latency-probe-based sizing step that picks the largest N whose estimated cache-miss cost fits a ~4-minute call budget (spec: full run under ~5 min).

**Tech Stack:** Python (anaconda interpreter `C:\Users\prith\anaconda3\python.exe` — the only env where the ionosphere backend works), numpy, pandas, pytest with mocked ionosphere.

## Global Constraints

- Script location: repo root `bearing_noise_study.py` (spec §3.2 — next to `report_table3.py`).
- Grid: `az_sigma ∈ {0, 0.5, 1.0, 2.0}°` × `el_sigma ∈ {0, 0.5, 1.0, 2.0}°` — 16 cells (spec §3.2).
- Noise: independent zero-mean Gaussian per axis; noisy elevation clipped to the solver's valid `1°–60°` band; noisy azimuth wrapped mod 360 (spec §3.2).
- The `(az_sigma=0, el_sigma=0)` cell is the intrinsic error floor (spec §3.2).
- Inputs: `data/processed/test_signals.csv` — generate via `build_test_signal_set()` if absent (spec §3.2).
- Outputs: 2D MAE table on stdout + per-trial `data/processed/bearing_noise_results.csv` (spec §3.2).
- Deterministic: `np.random.default_rng(42)`, fixed loop order (cells → signals → realizations).
- Memoization is installed **only inside the study** by monkeypatching `models.ssl_algorithm.get_ionosphere`; it must be restored on exit (even on exception). Production code untouched (spec §3.2, §6).
- Quantization: coordinates rounded to `0.1°` cells — documented as a deliberate, physically-justified optimization (spec §3.2).
- `N` sized against a **measured per-call latency probe** so the full run stays under ~5 minutes (spec §3.2).
- **Do not modify** `models/ssl_algorithm.py`, `models/hybrid_model.py`, `api/main.py`, model wrappers, or `data/generate_test_signals.py` (spec §6).
- Test command: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/ -q` from repo root.
- Commit messages: plain conventional commits, **no** Co-Authored-By or attribution lines.

## File Structure

- `bearing_noise_study.py` — new, repo root. Memoizer + trials loop + summary + sizing + CLI `main()`.
- `tests/test_bearing_noise_study.py` — new. Memoizer behavior, restore-on-exit, zero-noise floor, clipping, determinism — all with mocked ionosphere.
- `docs/bearing_noise_results.md` — new, written in Task 3 from the real run's numbers.
- Nothing else created or modified.

---

### Task 1: Memoizing ionosphere wrapper

**Files:**
- Create: `bearing_noise_study.py`
- Test: `tests/test_bearing_noise_study.py`

**Interfaces:**
- Consumes: `models.ssl_algorithm` module (patch target `models.ssl_algorithm.get_ionosphere`).
- Produces (Task 2/3 rely on these exact names):
  - `make_memoized(fn, quant_deg=0.1)` → wrapper with same keyword signature as `get_ionosphere`, plus `wrapper.stats = {"calls": int, "misses": int}`
  - `memoized_ionosphere(quant_deg=0.1)` — context manager that patches `models.ssl_algorithm.get_ionosphere` with the wrapper, yields the wrapper, restores the original in `finally`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bearing_noise_study.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_bearing_noise_study.py -q`
Expected: collection ERROR — `ModuleNotFoundError: No module named 'bearing_noise_study'`.

- [ ] **Step 3: Create the module with the memoizer**

Create `bearing_noise_study.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_bearing_noise_study.py -q`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add bearing_noise_study.py tests/test_bearing_noise_study.py
git commit -m "feat: add memoizing ionosphere wrapper for bearing-noise study"
```

---

### Task 2: Trial runner and summary tables

**Files:**
- Modify: `bearing_noise_study.py` (append)
- Test: `tests/test_bearing_noise_study.py` (append)

**Interfaces:**
- Consumes: Task 1's `memoized_ionosphere`; `ssl_locate(receiver_lat, receiver_lon, azimuth_deg, elevation_deg, frequency_mhz, dt, kp, dst, irtam_available=False) -> SSLResult`; `haversine_km` and `build_test_signal_set` from `data.generate_test_signals`.
- Produces (Task 3 relies on these exact names):
  - `run_trials(signals: pd.DataFrame, az_sigmas=AZ_SIGMAS, el_sigmas=EL_SIGMAS, n_realizations=20, seed=SEED) -> pd.DataFrame` with columns `az_sigma, el_sigma, signal_id, realization, emitter_lat, emitter_lon, azimuth_noisy_deg, elevation_noisy_deg, tx_lat, tx_lon, error_km, model_used, timestamp, kp, dst`
  - `summarize(trials: pd.DataFrame) -> dict[str, pd.DataFrame]` — keys `"MAE"`, `"median"`, `"P90"`, each a pivot with `az_sigma` rows × `el_sigma` columns of `error_km`, rounded to 1 dp.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bearing_noise_study.py`:

```python
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
```

Also add `import pandas as pd` to the test file's imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_bearing_noise_study.py -q`
Expected: 3 new FAILs with `ImportError: cannot import name 'run_trials'`; the 2 Task-1 tests still pass.

- [ ] **Step 3: Implement `run_trials` and `summarize`**

Append to `bearing_noise_study.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_bearing_noise_study.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add bearing_noise_study.py tests/test_bearing_noise_study.py
git commit -m "feat: add bearing-noise trial runner and summary tables"
```

---

### Task 3: Latency-probe sizing, CLI, and the real run

**Files:**
- Modify: `bearing_noise_study.py` (append)
- Test: `tests/test_bearing_noise_study.py` (append)

**Interfaces:**
- Consumes: everything above; `compute_transmitter_location` (for the dry-run midpoint estimate); the real `models.hybrid_model.get_ionosphere` (probe only).
- Produces:
  - `estimate_misses(signals, n_realizations, quant_deg=QUANT_DEG, assumed_height_km=300.0) -> int` — replays the exact trial loop (same seed/order) with pure geometry at a fixed height and counts unique quantized cache keys.
  - `choose_n_realizations(latency_s, signals) -> tuple[int, float]` — largest `N_CANDIDATES` entry whose `estimate_misses * 1.2 * latency_s <= CALL_BUDGET_S` (falls back to 1).
  - CLI `main()` → stdout tables + `data/processed/bearing_noise_results.csv`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_bearing_noise_study.py`:

```python
# ── Sizing ───────────────────────────────────────────────────────────────

def test_choose_n_scales_with_latency():
    """Fast model -> largest N; very slow model -> smallest N."""
    from bearing_noise_study import choose_n_realizations, N_CANDIDATES

    signals = _mini_signal_set()

    n_fast, _ = choose_n_realizations(latency_s=0.0001, signals=signals)
    assert n_fast == N_CANDIDATES[0]

    n_slow, _ = choose_n_realizations(latency_s=1000.0, signals=signals)
    assert n_slow == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_bearing_noise_study.py -q`
Expected: 1 new FAIL with `ImportError: cannot import name 'choose_n_realizations'`; 5 pass.

- [ ] **Step 3: Implement sizing and CLI**

Append to `bearing_noise_study.py`:

```python
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
```

- [ ] **Step 4: Run all tests**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/ -q`
Expected: 26 passed (6 study + 15 generator + 5 API).

- [ ] **Step 5: The real run**

Run: `"C:\Users\prith\anaconda3\python.exe" bearing_noise_study.py`
Expected: latency probe report, chosen N, progress, per-trial CSV saved, three 4×4 tables printed, total wall time under ~5–6 min. Record the printed MAE/median/P90 tables, N, intrinsic floor, and cache stats — Task 4 needs them verbatim.
If the run badly overshoots the budget (>2× estimate), stop and reassess the miss estimate rather than letting it grind.

Then verify determinism cheaply: re-running is expensive, so instead confirm the CSV row count equals `72 * 16 * N` and that the `(0,0)` cell's `error_km` values are all identical across realizations of the same signal.

- [ ] **Step 6: Commit**

```bash
git add bearing_noise_study.py tests/test_bearing_noise_study.py
git commit -m "feat: add bearing-noise study CLI with latency-sized realizations"
```

---

### Task 4: Results document

**Files:**
- Create: `docs/bearing_noise_results.md`

**Interfaces:**
- Consumes: the three printed tables, N, intrinsic floor value, and cache stats from Task 3 Step 5. **This document must contain the real run's numbers — never invented ones.**

- [ ] **Step 1: Write the document**

Create `docs/bearing_noise_results.md` with this structure, filling every `<...>` slot from the real run output:

```markdown
# Bearing-Noise Sensitivity Study — Results

**Problem ID:** DRDO DIA-CoE/EW/02
**Generated by:** `bearing_noise_study.py` (seed 42, N=<N> realizations/cell, <runtime>s wall time)
**Inputs:** `data/processed/test_signals.csv` — 72 ground-truth signals (8 azimuths × {800, 1500, 2200} km × 3 conditions, AH223 receiver)

## Figure of Merit: MAE (km) vs bearing error

| az_sigma \ el_sigma | 0.0° | 0.5° | 1.0° | 2.0° |
|---|---|---|---|---|
| **0.0°** | <..> | <..> | <..> | <..> |
| **0.5°** | <..> | <..> | <..> | <..> |
| **1.0°** | <..> | <..> | <..> | <..> |
| **2.0°** | <..> | <..> | <..> | <..> |

(median and P90 tables in the same format)

## Interpretation

- **Intrinsic floor:** the (0, 0) cell — <value> km MAE — is the algorithm's
  own error with perfect bearings: two-pass midpoint refinement +
  spherical-geometry approximation only.
- **Elevation dominates:** <describe the asymmetry with the actual numbers —
  compare (0, 2.0) vs (2.0, 0)>.
- **Azimuth mainly rotates the fix:** <actual numbers>.

## Scope and honesty

- Single-hop, mid-latitude India geometry only.
- Same-model isolation: observations are synthesized and inverted with the
  same hybrid ionosphere, so ionospheric *model* error is excluded by design —
  it is characterized separately in `docs/results.md` (Table 2/3 MAE).
- Elevation noise is clipped to the solver's validated 1°–60° band.
- Memoized ionosphere lookups quantized to 0.1° (~11 km) — well below the
  ionosphere's native spatial resolution; <misses> real model calls served
  <calls> lookups.
```

- [ ] **Step 2: Verify the document's numbers**

Cross-check every number in the doc against the Task 3 Step 5 output. The MAE table must match `summarize(trials)["MAE"]` exactly.

- [ ] **Step 3: Commit**

```bash
git add docs/bearing_noise_results.md
git commit -m "docs: add bearing-noise sensitivity study results"
```

---

## Spec coverage check

- §3.2 repo-root placement → Task 1.
- §3.2 load CSV / generate if absent → Task 3 `main()`.
- §3.2 4×4 sigma grid, N Gaussian realizations, clip to 1–60°, real `ssl_locate`, haversine error → Task 2.
- §3.2 MAE/median/P90 per cell, (0,0) intrinsic floor → Task 2 `summarize` + Task 4 doc.
- §3.2 stdout table + per-trial `bearing_noise_results.csv` → Task 3.
- §3.2 fixed seed, deterministic → Task 2 (+ determinism test).
- §3.2 memoizing monkeypatch, 0.1° quantization, production untouched → Task 1.
- §3.2 N sized by measured latency probe, run < ~5 min → Task 3.
- §3.3 results doc with intrinsic floor, az/el asymmetry, scope statements → Task 4.
- §6 surgical footprint → Global Constraints.
- §7 success criterion 3 (end-to-end < ~5 min, 4×4 grid + CSV, reproducible) → Task 3; criterion 4 (honest results doc) → Task 4.
