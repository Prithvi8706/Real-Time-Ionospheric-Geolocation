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
