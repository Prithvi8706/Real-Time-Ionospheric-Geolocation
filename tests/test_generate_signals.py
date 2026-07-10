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
