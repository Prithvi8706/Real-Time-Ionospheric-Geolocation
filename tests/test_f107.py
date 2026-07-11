"""
Unit + integration tests for the F10.7 OMNIWeb auto-lookup (TODOS item 4).

All network access is mocked — _fetch_year is the single touchpoint.

Run with:
    python -m pytest tests/test_f107.py -v
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest

import api.f107 as f107mod
from api.f107 import DEFAULT_F107, lookup_f107, resolve_f107


# Synthetic OMNI2 year: hourly rows, 55 columns, day 167 (=2012-06-15)
# carries F10.7=120.9, day 168 carries the 999.9 fill value.
def _omni2_line(year, doy, hour, f107):
    parts = ["0"] * 55
    parts[0], parts[1], parts[2] = str(year), str(doy), str(hour)
    parts[38], parts[40], parts[50] = "10", "-5", f"{f107:.1f}"
    return " ".join(parts)


_FAKE_2012 = "\n".join(
    [_omni2_line(2012, 167, h, 120.9) for h in range(24)]
    + [_omni2_line(2012, 168, h, 999.9) for h in range(24)]
)


@pytest.fixture(autouse=True)
def _clean_module_state():
    f107mod._cache.clear()
    f107mod._failed_years.clear()
    yield
    f107mod._cache.clear()
    f107mod._failed_years.clear()


def test_lookup_parses_and_caches():
    """First lookup fetches the year once; the second is served from cache."""
    with patch("api.f107._fetch_year", return_value=_FAKE_2012) as fetch:
        assert lookup_f107(date(2012, 6, 15)) == 120.9
        assert lookup_f107(date(2012, 6, 15)) == 120.9
    assert fetch.call_count == 1


def test_fill_value_is_rejected():
    """Day 168 carries the 999.9 OMNI fill value -> no usable data."""
    with patch("api.f107._fetch_year", return_value=_FAKE_2012):
        assert lookup_f107(date(2012, 6, 16)) is None


def test_fetch_failure_is_remembered():
    """A failed year returns None and is not re-fetched."""
    with patch("api.f107._fetch_year", side_effect=OSError("offline")) as fetch:
        assert lookup_f107(date(2012, 6, 15)) is None
        assert lookup_f107(date(2012, 6, 15)) is None
    assert fetch.call_count == 1


def test_resolve_prefers_caller_value():
    with patch("api.f107._fetch_year") as fetch:
        value, source = resolve_f107(180.0, datetime(2012, 6, 15, 12))
    assert (value, source) == (180.0, "caller")
    fetch.assert_not_called()


def test_resolve_uses_omniweb_when_omitted():
    with patch("api.f107._fetch_year", return_value=_FAKE_2012):
        value, source = resolve_f107(None, datetime(2012, 6, 15, 12))
    assert (value, source) == (120.9, "omniweb")


def test_resolve_falls_back_to_default():
    with patch("api.f107._fetch_year", side_effect=OSError("offline")):
        value, source = resolve_f107(None, datetime(2012, 6, 15, 12))
    assert (value, source) == (DEFAULT_F107, "default")


# ── /locate integration ──────────────────────────────────────────────────

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

_PAYLOAD_NO_F107 = {
    "receiver_lat": 23.0,
    "receiver_lon": 72.0,
    "azimuth_deg": 45.0,
    "elevation_deg": 15.0,
    "frequency_mhz": 10.0,
    "timestamp": "2012-06-15T12:00:00",
    "kp": 1.0,
    "dst": -10.0,
    "irtam_available": True,
}


def _mock_ssl():
    m = MagicMock()
    m.transmitter_lat = 24.5
    m.transmitter_lon = 73.5
    m.ground_distance_km = 180.0
    m.virtual_height_km = 280.0
    m.model_used = "IRTAM"
    m.selected_model = "IRTAM"
    m.reason = "nominal conditions, IRTAM available"
    m.foF2 = 12.0
    return m


def test_locate_omitted_f107_is_auto_resolved():
    with patch("api.main.ssl_locate", return_value=_mock_ssl()), \
         patch("api.main._gp_models_loaded", False), \
         patch("api.main.resolve_f107",
               return_value=(120.9, "omniweb")) as resolver:
        response = client.post("/locate", json=_PAYLOAD_NO_F107)

    assert response.status_code == 200
    data = response.json()
    assert data["f107_used"] == 120.9
    assert data["f107_source"] == "omniweb"
    (explicit, dt), _ = resolver.call_args
    assert explicit is None
    assert dt == datetime(2012, 6, 15, 12, 0, 0)


def test_locate_explicit_f107_is_respected():
    payload = {**_PAYLOAD_NO_F107, "f107": 180.0}
    with patch("api.main.ssl_locate", return_value=_mock_ssl()), \
         patch("api.main._gp_models_loaded", False), \
         patch("api.f107._fetch_year") as fetch:
        response = client.post("/locate", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["f107_used"] == 180.0
    assert data["f107_source"] == "caller"
    fetch.assert_not_called()


def test_locate_invalid_f107_still_422():
    payload = {**_PAYLOAD_NO_F107, "f107": 10.0}
    response = client.post("/locate", json=payload)
    assert response.status_code == 422
