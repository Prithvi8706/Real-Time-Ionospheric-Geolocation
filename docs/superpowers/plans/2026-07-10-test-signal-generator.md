# Test Signal Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `data/generate_test_signals.py` — the DRDO ground-truth test signal generator that places emitters at known positions and synthesizes the exact `(azimuth, elevation, frequency)` a receiver would observe, per §3.1 of `docs/superpowers/specs/2026-07-01-test-signal-generator-and-bearing-noise-study-design.md`.

**Architecture:** A library module with three pure great-circle geometry helpers (haversine range, initial bearing, midpoint), a `synthesize_observation()` function that runs forward geometry through the real hybrid ionosphere (`get_ionosphere` at the bounce midpoint, height via the solver's own `_extract_height`), and a CLI that sweeps a fixed emitter grid and writes `data/processed/test_signals.csv`. The generator is the exact inverse of the solver: `elevation = atan(h / ground_range)` inverts `ground_distance = h / tan(elevation)`, and haversine/bearing invert `compute_transmitter_location` on the same 6371.0 km sphere.

**Tech Stack:** Python, numpy, pandas, pytest (with `unittest.mock.patch` for the ionosphere). No new dependencies.

## Global Constraints

- Receiver is AH223 Ahmedabad: lat `23.0`, lon `72.6` (spec §3.1).
- Solver's validated elevation band is `1.0°`–`60.0°`; out-of-band synthesized signals are dropped with a logged count (spec §3.1).
- Emitter grid: azimuths every `45°` (0–315), ground ranges `{800, 1500, 2200}` km, representative 2012 conditions (spec §3.1).
- Reproducibility: `np.random.seed(42)` at the top of the set builder (spec §3.1).
- Earth radius: import `EARTH_RADIUS_KM` from `models.ssl_algorithm` — never redefine it. Generator and solver must share one sphere.
- **Do not modify** `models/ssl_algorithm.py`, `models/hybrid_model.py`, `api/main.py`, or any model wrapper (spec §6).
- Output CSV: `data/processed/test_signals.csv`.
- Known environment limitation: the local ionosphere backend is unavailable (the `/locate` endpoint 503s locally because IRI profiles come back null). All unit tests therefore mock `get_ionosphere`; the real CLI run only succeeds where the model backend works. Never fake or hand-write the CSV if the real run fails — report the failure instead.
- Commit messages: plain conventional commits, **no** Co-Authored-By or any attribution lines.
- Run tests from the repo root: `python -m pytest tests/test_generate_signals.py -v` (matches how `tests/test_ssl.py` resolves imports).

## File Structure

- `data/generate_test_signals.py` — new. Geometry helpers, `ObservationTruth` dataclass, `synthesize_observation()`, `build_test_signal_set()`, CLI `main()`. Follows the sibling-script convention (`data/simulate_ssl_dataset.py`): `sys.path` bootstrap at top, flat script style.
- `tests/test_generate_signals.py` — new. All unit tests for the generator (geometry inverses, zero-noise recovery, elevation-band guard), mocked ionosphere throughout.
- Nothing else is created or modified.

---

### Task 1: Great-circle geometry helpers

**Files:**
- Create: `data/generate_test_signals.py`
- Test: `tests/test_generate_signals.py`

**Interfaces:**
- Consumes: `compute_transmitter_location(receiver_lat, receiver_lon, azimuth_deg, ground_distance_km) -> tuple[float, float]` and `EARTH_RADIUS_KM` from `models/ssl_algorithm.py` (already exist).
- Produces (Task 2 and 3 rely on these exact names):
  - `haversine_km(lat1, lon1, lat2, lon2) -> float`
  - `initial_bearing_deg(lat1, lon1, lat2, lon2) -> float` (normalized to `[0, 360)`)
  - `gc_midpoint(lat1, lon1, lat2, lon2) -> tuple[float, float]`

- [ ] **Step 1: Write the failing round-trip test**

Create `tests/test_generate_signals.py`:

```python
"""
Unit tests for the DRDO test signal generator.

The ionosphere backend is unavailable locally, so every test that touches
get_ionosphere mocks it. Geometry tests are pure math and need no mocks.

Run with:
    python -m pytest tests/test_generate_signals.py -v
"""

import pytest

from models.ssl_algorithm import compute_transmitter_location
from data.generate_test_signals import (
    haversine_km,
    initial_bearing_deg,
    gc_midpoint,
)

RX_LAT, RX_LON = 23.0, 72.6  # AH223 Ahmedabad


def _angle_diff_deg(a: float, b: float) -> float:
    """Smallest signed angular difference a-b in degrees."""
    return ((a - b + 180.0) % 360.0) - 180.0


# ── Spec test 1: pure-geometry round trip is exact ───────────────────────

@pytest.mark.parametrize("az,dist_km", [
    (0.0, 800.0),
    (45.0, 1500.0),
    (135.0, 2200.0),
    (270.0, 1000.0),
    (359.0, 800.0),
])
def test_geometry_round_trip(az, dist_km):
    """
    compute_transmitter_location followed by haversine range + initial
    bearing back from the receiver recovers (az, dist) to fp tolerance.
    """
    em_lat, em_lon = compute_transmitter_location(RX_LAT, RX_LON, az, dist_km)

    recovered_dist = haversine_km(RX_LAT, RX_LON, em_lat, em_lon)
    recovered_az = initial_bearing_deg(RX_LAT, RX_LON, em_lat, em_lon)

    assert recovered_dist == pytest.approx(dist_km, abs=1e-5)
    assert _angle_diff_deg(recovered_az, az) == pytest.approx(0.0, abs=1e-6)


def test_gc_midpoint_is_equidistant():
    """The great-circle midpoint is the same haversine distance from both ends."""
    em_lat, em_lon = compute_transmitter_location(RX_LAT, RX_LON, 45.0, 1500.0)
    mid_lat, mid_lon = gc_midpoint(RX_LAT, RX_LON, em_lat, em_lon)

    d1 = haversine_km(RX_LAT, RX_LON, mid_lat, mid_lon)
    d2 = haversine_km(mid_lat, mid_lon, em_lat, em_lon)

    assert d1 == pytest.approx(d2, abs=1e-5)
    assert d1 == pytest.approx(750.0, abs=1e-3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_generate_signals.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'data.generate_test_signals'` (or ImportError).

- [ ] **Step 3: Create the module with the geometry helpers**

Create `data/generate_test_signals.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate_signals.py -v`
Expected: 6 PASSED (5 round-trip parametrizations + midpoint test).

- [ ] **Step 5: Commit**

```bash
git add data/generate_test_signals.py tests/test_generate_signals.py
git commit -m "feat: add great-circle geometry helpers for test signal generator"
```

---

### Task 2: `synthesize_observation` — forward geometry through the ionosphere

**Files:**
- Modify: `data/generate_test_signals.py` (append after `gc_midpoint`)
- Test: `tests/test_generate_signals.py` (append)

**Interfaces:**
- Consumes: Task 1 helpers; `get_ionosphere(lat, lon, dt, kp, dst, irtam_available) -> dict` (keys `model_used`, `selected_model`, `reason`, `profile`); `_extract_height(profile) -> float`; `compute_ground_distance(virtual_height_km, elevation_deg) -> float` and `ssl_locate(...)` from `models.ssl_algorithm` (tests only).
- Produces (Task 3 relies on these exact names):
  - `@dataclass ObservationTruth` with fields `emitter_lat, emitter_lon, receiver_lat, receiver_lon, azimuth_deg, elevation_deg, frequency_mhz, ground_range_km, virtual_height_km, model_used, dt, kp, dst`
  - `synthesize_observation(emitter_lat, emitter_lon, receiver_lat, receiver_lon, frequency_mhz, dt, kp, dst, irtam_available=False) -> ObservationTruth`

**Mock-patch targets (critical):** the generator imports `get_ionosphere` into its own namespace, so patch `data.generate_test_signals.get_ionosphere`. `ssl_locate` resolves its own import, so patch `models.ssl_algorithm.get_ionosphere` separately. Patching only one of the two silently tests nothing.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_signals.py`:

```python
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from models.ssl_algorithm import compute_ground_distance, ssl_locate

DT = datetime(2012, 6, 15, 12, 0, 0)


def _iono(height_km: float) -> dict:
    """Fake get_ionosphere() return with a fixed hmF2 height."""
    return {
        "model_used": "IRTAM",
        "selected_model": "IRTAM",
        "reason": "test fixture",
        "profile": SimpleNamespace(
            hmF2=height_km, virtual_height_km=None, foF2=8.0
        ),
    }


# ── Spec test 2: height/elevation inverse is exact ───────────────────────

@pytest.mark.parametrize("h,el", [
    (250.0, 5.0),
    (300.0, 15.0),
    (350.0, 30.0),
    (400.0, 59.0),
])
def test_height_elevation_inverse(h, el):
    """
    elevation = atan(h / d) is the exact inverse of the solver's
    d = h / tan(elevation).
    """
    d = compute_ground_distance(h, el)
    recovered_el = float(np.degrees(np.arctan(h / d)))
    assert recovered_el == pytest.approx(el, abs=1e-9)


# ── synthesize_observation truth fields ──────────────────────────────────

def test_synthesize_observation_fields():
    """Truth record carries exact range/bearing and the mocked model height."""
    from data.generate_test_signals import synthesize_observation

    em_lat, em_lon = compute_transmitter_location(RX_LAT, RX_LON, 45.0, 1500.0)

    with patch("data.generate_test_signals.get_ionosphere", return_value=_iono(300.0)):
        obs = synthesize_observation(
            em_lat, em_lon, RX_LAT, RX_LON,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
        )

    assert obs.emitter_lat == em_lat
    assert obs.emitter_lon == em_lon
    assert obs.ground_range_km == pytest.approx(1500.0, abs=1e-5)
    assert _angle_diff_deg(obs.azimuth_deg, 45.0) == pytest.approx(0.0, abs=1e-6)
    assert obs.virtual_height_km == 300.0
    assert obs.model_used == "IRTAM"
    expected_el = float(np.degrees(np.arctan(300.0 / obs.ground_range_km)))
    assert obs.elevation_deg == pytest.approx(expected_el, abs=1e-9)


# ── Spec test 3: zero-noise recovery is bounded ──────────────────────────

def test_zero_noise_recovery_constant_height():
    """
    With a constant-height ionosphere the solver's two passes see the same
    height, so feeding a synthesized clean observation through ssl_locate
    recovers the emitter almost exactly (only SSLResult's 4-dp coordinate
    rounding remains, ~11 m).
    """
    from data.generate_test_signals import synthesize_observation

    em_lat, em_lon = compute_transmitter_location(RX_LAT, RX_LON, 45.0, 1500.0)

    with patch("data.generate_test_signals.get_ionosphere", return_value=_iono(300.0)), \
         patch("models.ssl_algorithm.get_ionosphere", return_value=_iono(300.0)):
        obs = synthesize_observation(
            em_lat, em_lon, RX_LAT, RX_LON,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
        )
        result = ssl_locate(
            RX_LAT, RX_LON, obs.azimuth_deg, obs.elevation_deg,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
        )

    err_km = haversine_km(em_lat, em_lon, result.transmitter_lat, result.transmitter_lon)
    assert err_km < 1.0


def test_zero_noise_recovery_varying_height_bounded():
    """
    With a latitude-dependent height the solver's two-pass refinement is an
    approximation of the generator's true-midpoint query, so recovery is
    NOT exact — assert only a loose documented bound (spec §5.3). The exact
    magnitude is an empirical result for the bearing-noise study, not a
    unit-test invariant.
    """
    from data.generate_test_signals import synthesize_observation

    def varying_iono(lat, lon, dt, kp, dst, irtam_available=False):
        return _iono(300.0 + 2.0 * (lat - RX_LAT))

    em_lat, em_lon = compute_transmitter_location(RX_LAT, RX_LON, 45.0, 1500.0)

    with patch("data.generate_test_signals.get_ionosphere", side_effect=varying_iono), \
         patch("models.ssl_algorithm.get_ionosphere", side_effect=varying_iono):
        obs = synthesize_observation(
            em_lat, em_lon, RX_LAT, RX_LON,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
        )
        result = ssl_locate(
            RX_LAT, RX_LON, obs.azimuth_deg, obs.elevation_deg,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
        )

    err_km = haversine_km(em_lat, em_lon, result.transmitter_lat, result.transmitter_lon)
    assert err_km < 25.0
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/test_generate_signals.py -v`
Expected: the 4 `test_height_elevation_inverse` cases PASS (pure solver math, no new code needed); `test_synthesize_observation_fields` and both recovery tests FAIL with `ImportError: cannot import name 'synthesize_observation'`.

- [ ] **Step 3: Implement `ObservationTruth` and `synthesize_observation`**

Append to `data/generate_test_signals.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate_signals.py -v`
Expected: 13 PASSED (6 from Task 1 + 4 inverse + fields + 2 recovery).

- [ ] **Step 5: Commit**

```bash
git add data/generate_test_signals.py tests/test_generate_signals.py
git commit -m "feat: add synthesize_observation forward-geometry truth generator"
```

---

### Task 3: Emitter grid, elevation-band guard, and CSV CLI

**Files:**
- Modify: `data/generate_test_signals.py` (append after `synthesize_observation`)
- Test: `tests/test_generate_signals.py` (append)

**Interfaces:**
- Consumes: `synthesize_observation` and `compute_transmitter_location` (emitters are *placed* by moving from the receiver along a chosen azimuth/range on the solver's own sphere, so the known position is exact by construction).
- Produces:
  - `build_test_signal_set(receiver_lat=RECEIVER_LAT, receiver_lon=RECEIVER_LON, azimuths_deg=AZIMUTHS_DEG, ground_ranges_km=GROUND_RANGES_KM, conditions=CONDITIONS, frequency_mhz=FREQUENCY_MHZ) -> pd.DataFrame`
  - CSV at `data/processed/test_signals.csv` with columns: `emitter_lat, emitter_lon, receiver_lat, receiver_lon, azimuth_deg, elevation_deg, frequency_mhz, ground_range_km, virtual_height_km, model_used, timestamp, kp, dst` (`timestamp` is `dt.isoformat()`; the bearing-noise study parses it back).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_generate_signals.py`:

```python
# ── Elevation-band guard + CSV set builder ───────────────────────────────

EXPECTED_COLUMNS = [
    "emitter_lat", "emitter_lon", "receiver_lat", "receiver_lon",
    "azimuth_deg", "elevation_deg", "frequency_mhz",
    "ground_range_km", "virtual_height_km", "model_used",
    "timestamp", "kp", "dst",
]


def test_elevation_band_guard_drops_out_of_band():
    """
    100 km range -> elevation ~71.6 deg (>60), 20000 km -> ~0.86 deg (<1):
    both must be dropped; only the 800 km emitter survives.
    """
    from data.generate_test_signals import build_test_signal_set

    with patch("data.generate_test_signals.get_ionosphere", return_value=_iono(300.0)):
        df = build_test_signal_set(
            azimuths_deg=[90.0],
            ground_ranges_km=[100.0, 800.0, 20000.0],
            conditions=[{"dt": DT, "kp": 1.0, "dst": -10.0}],
        )

    assert len(df) == 1
    assert list(df.columns) == EXPECTED_COLUMNS
    assert df["elevation_deg"].between(1.0, 60.0).all()


def test_build_full_default_grid():
    """Default grid: 8 azimuths x 3 ranges x 3 conditions, all in-band at h=300 km."""
    from data.generate_test_signals import build_test_signal_set

    with patch("data.generate_test_signals.get_ionosphere", return_value=_iono(300.0)):
        df = build_test_signal_set()

    assert len(df) == 72
    assert df["elevation_deg"].between(1.0, 60.0).all()
    assert (df["receiver_lat"] == RX_LAT).all()
    assert (df["receiver_lon"] == RX_LON).all()
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/test_generate_signals.py -v`
Expected: the 2 new tests FAIL with `ImportError: cannot import name 'build_test_signal_set'`; the 13 earlier tests still PASS.

- [ ] **Step 3: Implement the set builder and CLI**

Append to `data/generate_test_signals.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_generate_signals.py -v`
Expected: 15 PASSED.

Also run the existing suite to confirm nothing regressed:

Run: `python -m pytest tests/ -v`
Expected: all PASSED (15 new + 5 existing in `test_ssl.py`).

- [ ] **Step 5: Attempt the real CLI run**

Run: `python data/generate_test_signals.py`
Expected where the model backend works: `Saved 72 test signals to ...test_signals.csv` (possibly fewer with a logged drop count if real heights push edge geometries out of band).
Known local limitation: the ionosphere backend is unavailable locally (IRI returns null profiles → `_extract_height` raises HTTPException 503). If that happens: do **not** fabricate the CSV — report that the generator is complete and tested but the CSV must be produced on a machine with a working model backend.

- [ ] **Step 6: Commit**

```bash
git add data/generate_test_signals.py tests/test_generate_signals.py
git commit -m "feat: add test signal CSV generation CLI with elevation-band guard"
```

---

## Spec coverage check

- §3.1 library function `synthesize_observation` with exact signature → Task 2.
- §3.1 forward geometry steps 1–5 (haversine, bearing, midpoint, `_extract_height`, `atan(h/d)`) → Tasks 1–2.
- §3.1 `ObservationTruth` dataclass fields → Task 2.
- §3.1 CLI → `data/processed/test_signals.csv`, seed 42, 45° azimuths × {800, 1500, 2200} km × 2012 conditions, AH223 receiver → Task 3.
- §3.1 elevation-band guard with logged drop count → Task 3.
- §5 test 1 (pure-geometry round trip) → Task 1.
- §5 test 2 (height/elevation inverse) → Task 2.
- §5 test 3 (bounded zero-noise recovery) → Task 2 (constant-height near-exact + varying-height loose bound).
- §6 surgical footprint (no solver/API/model changes) → enforced in Global Constraints.
- §7 success criterion 1 (reproducible CSV, all elevations in band) → Task 3; criterion 2 (unit tests pass) → Tasks 1–2.
- Out of scope for this plan (separate deliverable): `bearing_noise_study.py` (§3.2) and `docs/bearing_noise_results.md` (§3.3).
