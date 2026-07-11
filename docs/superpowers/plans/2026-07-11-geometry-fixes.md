# Two-Pass Geometry Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix TODOS.md items 1 and 2 — the two-call model inconsistency at the ±60° latitude boundary and the antimeridian midpoint longitude arithmetic in `ssl_locate`.

**Architecture:** (1) `get_ionosphere` gains an optional `force_model` parameter that skips `select_model` and pins the branch (fallback machinery untouched); `ssl_locate`'s refined pass passes `force_model=iono_init["selected_model"]` so both passes always attempt the same model. (2) The refined-pass midpoint longitude switches from arithmetic mean to a circular mean (`_circular_mean_deg` helper in `ssl_algorithm.py`), which is exact for the mid-latitude case (identical bisector when the angular gap < 180°) and additionally normalizes the midpoint into [−180, 180] before it reaches the ionospheric models. The bearing-noise study's memoizing wrapper and existing test fakes gain `**kwargs` so the new keyword flows through them.

**Tech Stack:** numpy, pytest. Interpreter: `"C:\Users\prith\anaconda3\python.exe"`.

## Global Constraints

- At AH223 India geometry the numerical results must be unchanged (SSLResult rounds coordinates to 4 dp; the circular mean equals the arithmetic mean exactly in the bisector sense for close longitudes) — the full existing suite (35 tests) must pass untouched except the two test fakes gaining `**kwargs`.
- `force_model=None` default preserves every existing call path.
- The pinned refined pass keeps the runtime fallback (e.g. pinned IRTAM with missing coefficients still falls back to IRI); the pin fixes the *selection*, not the outcome.
- Do not change the midpoint latitude arithmetic (still the plain average) — surgical scope.
- Commit messages: plain conventional commits, no attribution lines.
- Tests from repo root: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/ -q`.

## File Structure

- `models/ssl_algorithm.py` — add `_circular_mean_deg`, use it for `mid_lon`, pass `force_model` on the refined call.
- `models/hybrid_model.py` — `get_ionosphere(..., force_model=None)`.
- `bearing_noise_study.py` — memoizer wrapper accepts/keys `**kwargs`.
- `tests/test_generate_signals.py`, `tests/test_bearing_noise_study.py` — `varying_iono` fakes accept `**kwargs`.
- `tests/test_geometry_fixes.py` — new tests.
- `TODOS.md` — mark items 1 and 2 resolved.

---

### Task 1: Antimeridian-safe midpoint (circular mean)

**Files:**
- Modify: `models/ssl_algorithm.py:114-116`
- Test: `tests/test_geometry_fixes.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_geometry_fixes.py`:

```python
"""
Tests for the two-pass geometry fixes (TODOS items 1 and 2):
antimeridian-safe midpoint longitude and two-pass model consistency.

Run with:
    python -m pytest tests/test_geometry_fixes.py -v
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from models.ssl_algorithm import _circular_mean_deg, ssl_locate

DT = datetime(2012, 6, 15, 12, 0, 0)


def _iono(height_km=300.0, selected="IRTAM", used="IRTAM"):
    return {
        "model_used": used,
        "selected_model": selected,
        "reason": "test fixture",
        "profile": SimpleNamespace(
            hmF2=height_km, virtual_height_km=None, foF2=8.0
        ),
    }


# ── TODOS item 2: circular mean for midpoint longitude ───────────────────

@pytest.mark.parametrize("a,b,expected", [
    (10.0, 20.0, 15.0),      # ordinary case = arithmetic mean
    (-10.0, 10.0, 0.0),
    (170.0, -170.0, 180.0),  # the TODOS example: NOT 0
    (179.0, 195.0, -173.0),  # unnormalized input from compute_transmitter_location
])
def test_circular_mean_deg(a, b, expected):
    got = _circular_mean_deg(a, b)
    # compare on the circle (180 == -180)
    diff = abs((got - expected + 180.0) % 360.0 - 180.0)
    assert diff < 1e-9


def test_ssl_locate_midpoint_is_antimeridian_safe():
    """
    Receiver near the antimeridian, emitter across it: the refined-pass
    ionosphere query must receive a normalized longitude near ±180,
    never a wrapped-to-0 or out-of-range value.
    """
    calls = []

    def capture(lat, lon, dt, kp, dst, irtam_available=False, **kwargs):
        calls.append({"lat": lat, "lon": lon, **kwargs})
        return _iono()

    with patch("models.ssl_algorithm.get_ionosphere", side_effect=capture):
        ssl_locate(
            receiver_lat=10.0, receiver_lon=179.0,
            azimuth_deg=90.0, elevation_deg=10.0,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
        )

    mid_lon = calls[1]["lon"]
    assert -180.0 <= mid_lon <= 180.0
    assert abs(mid_lon) > 170.0  # near the antimeridian, not near 0


# ── TODOS item 1: two-pass model consistency ─────────────────────────────

def test_ssl_locate_pins_refined_pass_to_rough_selection():
    """The refined call must carry force_model = rough pass's selected_model."""
    calls = []

    def capture(lat, lon, dt, kp, dst, irtam_available=False, **kwargs):
        calls.append(kwargs)
        return _iono(selected="IRTAM", used="IRTAM")

    with patch("models.ssl_algorithm.get_ionosphere", side_effect=capture):
        ssl_locate(
            receiver_lat=58.0, receiver_lon=20.0,
            azimuth_deg=0.0, elevation_deg=5.0,
            frequency_mhz=10.0, dt=DT, kp=1.0, dst=-10.0,
            irtam_available=True,
        )

    assert "force_model" not in calls[0] or calls[0].get("force_model") is None
    assert calls[1]["force_model"] == "IRTAM"


def test_get_ionosphere_force_model_overrides_latitude_rule():
    """
    force_model='IRI' at lat 65 (which would normally select A-CHAIM)
    must run the IRI branch. Real IRI call — works in the anaconda env.
    """
    from models.hybrid_model import get_ionosphere

    result = get_ionosphere(lat=65.0, lon=20.0, dt=DT, kp=1.0, dst=-10.0,
                            force_model="IRI")
    assert result["selected_model"] == "IRI"
    assert result["model_used"] == "IRI"
    assert "pinned" in result["reason"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_geometry_fixes.py -q`
Expected: collection ERROR — `ImportError: cannot import name '_circular_mean_deg'`.

- [ ] **Step 3: Implement the circular mean in `models/ssl_algorithm.py`**

Add after `compute_transmitter_location`:

```python
def _circular_mean_deg(a_deg: float, b_deg: float) -> float:
    """
    Circular mean of two longitudes, safe across the ±180° antimeridian
    and normalizing into [-180, 180]. For |a-b| < 180° this is exactly the
    arithmetic bisector, so mid-latitude behaviour is unchanged.
    """
    a = np.radians(a_deg)
    b = np.radians(b_deg)
    return float(np.degrees(np.arctan2(
        (np.sin(a) + np.sin(b)) / 2.0,
        (np.cos(a) + np.cos(b)) / 2.0,
    )))
```

Replace the midpoint computation in `ssl_locate` (Step 1b):

```python
    # Step 1b: Compute midpoint between receiver and rough transmitter.
    # Longitude uses a circular mean — antimeridian-safe and normalized
    # into [-180, 180] before it reaches the ionospheric models.
    mid_lat = (receiver_lat + rough_tx_lat) / 2
    mid_lon = _circular_mean_deg(receiver_lon, rough_tx_lon)
```

- [ ] **Step 4: Run the two midpoint tests**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/test_geometry_fixes.py -q`
Expected: the 4 `test_circular_mean_deg` cases and `test_ssl_locate_midpoint_is_antimeridian_safe` PASS; the two model-consistency tests still FAIL (no `force_model` yet).

- [ ] **Step 5: Commit**

```bash
git add models/ssl_algorithm.py tests/test_geometry_fixes.py
git commit -m "fix: antimeridian-safe circular-mean midpoint longitude in ssl_locate"
```

---

### Task 2: Two-pass model consistency (`force_model`)

**Files:**
- Modify: `models/hybrid_model.py` (signature + selection), `models/ssl_algorithm.py` (refined call), `bearing_noise_study.py` (wrapper), `tests/test_generate_signals.py` + `tests/test_bearing_noise_study.py` (fakes)

**Interfaces:**
- Produces: `get_ionosphere(lat, lon, dt, kp, dst, irtam_available=False, force_model=None)`; when `force_model` is set, selection is skipped and `reason` contains `"pinned"`.

- [ ] **Step 1: Modify `models/hybrid_model.py`**

Signature:

```python
def get_ionosphere(
    lat: float,
    lon: float,
    dt: datetime,
    kp: float,
    dst: float,
    irtam_available: bool = False,
    force_model: str = None
) -> dict:
```

Selection block (replacing the single `select_model` line):

```python
    if force_model is not None:
        # Two-pass consistency (TODOS item 1): the refined SSL pass pins the
        # model chosen by the rough pass so a midpoint that crosses the ±60°
        # boundary cannot silently mix model families. Fallback still applies.
        selection = SelectionResult(
            model=force_model,
            reason=f"pinned to rough-pass selection ({force_model}) "
                   "for two-pass consistency",
        )
    else:
        selection = select_model(lat, kp, dst, irtam_available)
    logger.info(f"Model selected: {selection.model} | {selection.reason}")
```

- [ ] **Step 2: Modify `ssl_locate`'s refined call in `models/ssl_algorithm.py`**

```python
    # Step 1c: Re-query ionosphere at midpoint (bounce point), pinned to the
    # rough pass's model selection (TODOS item 1: two-pass consistency)
    iono = get_ionosphere(
        lat=mid_lat,
        lon=mid_lon,
        dt=dt,
        kp=kp,
        dst=dst,
        irtam_available=irtam_available,
        force_model=iono_init["selected_model"]
    )
```

- [ ] **Step 3: Flow the new kwarg through the study memoizer and test fakes**

`bearing_noise_study.py` — wrapper becomes:

```python
    def wrapper(lat, lon, dt, kp, dst, irtam_available=False, **kwargs):
        stats["calls"] += 1
        key = (round(lat / quant_deg), round(lon / quant_deg),
               dt, kp, dst, irtam_available, tuple(sorted(kwargs.items())))
        if key not in cache:
            stats["misses"] += 1
            cache[key] = fn(lat=lat, lon=lon, dt=dt, kp=kp, dst=dst,
                            irtam_available=irtam_available, **kwargs)
        return cache[key]
```

`tests/test_generate_signals.py` — `varying_iono` in `test_zero_noise_recovery_varying_height_bounded` becomes:

```python
    def varying_iono(lat, lon, dt, kp, dst, irtam_available=False, **kwargs):
        return _iono(300.0 + 2.0 * (lat - RX_LAT))
```

(`unittest.mock.patch(..., return_value=...)` fakes are MagicMocks and already accept any kwargs — only the plain-function fakes need `**kwargs`.)

- [ ] **Step 4: Run the full suite**

Run: `"C:\Users\prith\anaconda3\python.exe" -m pytest tests/ -q`
Expected: 42 passed (7 new + 35 existing).

- [ ] **Step 5: Commit**

```bash
git add models/hybrid_model.py models/ssl_algorithm.py bearing_noise_study.py tests/test_generate_signals.py tests/test_geometry_fixes.py
git commit -m "fix: pin refined SSL pass to rough-pass model selection"
```

---

### Task 3: TODOS bookkeeping

**Files:**
- Modify: `TODOS.md` items 1 and 2

- [ ] **Step 1: Mark both items resolved**

```markdown
### 1. Two-call model inconsistency
**Resolved 2026-07-11** — the refined pass now pins the rough pass's model
selection via `get_ionosphere(force_model=...)`, so a midpoint crossing the
±60° boundary can no longer silently mix model families. Runtime fallback
(e.g. IRTAM → IRI on missing coefficients) still applies within the pinned
branch.

### 2. Antimeridian longitude midpoint arithmetic
**Resolved 2026-07-11** — the refined-pass midpoint longitude now uses a
circular mean (`_circular_mean_deg`), which is exactly the arithmetic
bisector at mid-latitudes (validated numbers unchanged) and additionally
normalizes the midpoint into [-180, 180] before it reaches the models.
```

- [ ] **Step 2: Commit**

```bash
git add TODOS.md docs/superpowers/plans/2026-07-11-geometry-fixes.md
git commit -m "docs: mark TODOS geometry items resolved"
```
