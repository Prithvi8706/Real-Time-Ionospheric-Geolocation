"""
Tests for D8: PyRayHF parameterised to the request frequency.

The wrapper test ray-traces for real (PyRayHF + iri2016 work in this env).
Threading tests use mocks.

Run with:
    python -m pytest tests/test_d8_frequency.py -v
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Solar-max local noon at AH223: foF2 well above 10 MHz, so both
# frequencies reflect and the higher one reflects higher.
DT_NOON = datetime(2012, 6, 15, 7, 0, 0)  # ~12:00 LT at 72.6 E


def test_rayhf_frequency_changes_virtual_height():
    from models.rayhf.rayhf_wrapper import get_rayhf_profile, is_rayhf_available

    p5 = get_rayhf_profile(23.0, 72.6, DT_NOON, frequency_mhz=5.0)
    p10 = get_rayhf_profile(23.0, 72.6, DT_NOON, frequency_mhz=10.0)

    assert is_rayhf_available(p5)
    assert is_rayhf_available(p10)
    # a higher frequency penetrates deeper before reflecting
    assert p10.virtual_height_km > p5.virtual_height_km


def test_rayhf_default_frequency_is_5mhz():
    from models.rayhf.rayhf_wrapper import get_rayhf_profile

    p_default = get_rayhf_profile(23.0, 72.6, DT_NOON)
    p5 = get_rayhf_profile(23.0, 72.6, DT_NOON, frequency_mhz=5.0)
    assert p_default.virtual_height_km == p5.virtual_height_km


def test_rayhf_penetrating_frequency_is_unavailable():
    """20 MHz > foF2 (~10.6 MHz at this hour): the ray escapes and the
    wrapper must report no usable virtual height, not a bogus integral."""
    from models.rayhf.rayhf_wrapper import get_rayhf_profile, is_rayhf_available

    p20 = get_rayhf_profile(23.0, 72.6, DT_NOON, frequency_mhz=20.0)
    assert not is_rayhf_available(p20)


def _iono(height_km=300.0):
    return {
        "model_used": "PyRayHF",
        "selected_model": "PyRayHF",
        "reason": "test fixture",
        "profile": SimpleNamespace(
            hmF2=height_km, virtual_height_km=height_km + 40.0, foF2=8.0
        ),
    }


def test_ssl_locate_passes_frequency_to_ionosphere():
    from models.ssl_algorithm import ssl_locate

    calls = []

    def capture(lat, lon, dt, kp, dst, irtam_available=False, **kwargs):
        calls.append(kwargs)
        return _iono()

    with patch("models.ssl_algorithm.get_ionosphere", side_effect=capture):
        ssl_locate(
            receiver_lat=22.5, receiver_lon=88.3,
            azimuth_deg=90.0, elevation_deg=10.0,
            frequency_mhz=15.0, dt=DT_NOON, kp=6.0, dst=-120.0,
        )

    assert calls[0]["frequency_mhz"] == 15.0
    assert calls[1]["frequency_mhz"] == 15.0


def test_get_ionosphere_forwards_frequency_to_rayhf_only():
    from models.hybrid_model import get_ionosphere

    fake_profile = SimpleNamespace(
        lat=22.5, lon=88.3, datetime=DT_NOON,
        virtual_height_km=350.0, hmF2=300.0, foF2=8.0, NmF2=1e12,
    )
    with patch("models.hybrid_model.get_rayhf_profile",
               return_value=fake_profile) as rayhf:
        out = get_ionosphere(lat=22.5, lon=88.3, dt=DT_NOON,
                             kp=6.0, dst=-120.0, frequency_mhz=15.0)

    assert out["model_used"] == "PyRayHF"
    assert rayhf.call_args.kwargs["frequency_mhz"] == 15.0
