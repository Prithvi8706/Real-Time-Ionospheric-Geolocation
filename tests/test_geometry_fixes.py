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
