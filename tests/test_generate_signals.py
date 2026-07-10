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
