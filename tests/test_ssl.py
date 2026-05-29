"""
Regression tests for the SSL geolocation pipeline.
Covers D1/D2/D3 fixes and core routing behaviour.

Run with:
    python -m pytest tests/test_ssl.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# ── Shared valid payload ─────────────────────────────────────────────────
_BASE_PAYLOAD = {
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


# ── Test 1: Sunny-day IRTAM + GP path ────────────────────────────────────

def test_sunny_day_irtam_gp():
    """
    Nominal request with IRTAM available and calm conditions.
    Expects 200, model_used='IRTAM', GP status='applied'.
    """
    mock_ssl = MagicMock()
    mock_ssl.transmitter_lat = 24.5
    mock_ssl.transmitter_lon = 73.5
    mock_ssl.ground_distance_km = 180.0
    mock_ssl.virtual_height_km = 280.0
    mock_ssl.model_used = "IRTAM"
    mock_ssl.selected_model = "IRTAM"
    mock_ssl.reason = "nominal conditions, IRTAM available"
    mock_ssl.foF2 = 12.0

    mock_gp_lat = MagicMock()
    mock_gp_lat.predict.return_value = ([0.05], [0.02])
    mock_gp_lat.X_train_ = MagicMock()
    mock_gp_lat.X_train_.shape = (9228, 10)

    mock_gp_lon = MagicMock()
    mock_gp_lon.predict.return_value = ([0.03], [0.02])
    mock_gp_lon.X_train_ = MagicMock()
    mock_gp_lon.X_train_.shape = (9228, 10)

    with patch("api.main.ssl_locate", return_value=mock_ssl), \
         patch("api.main._gp_lat_irtam", mock_gp_lat), \
         patch("api.main._gp_lon_irtam", mock_gp_lon), \
         patch("api.main._gp_models_loaded", True):

        response = client.post("/locate", json=_BASE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ionosphere"]["model_used"] == "IRTAM"
    assert data["ionosphere"]["selected_model"] == "IRTAM"
    assert data["gp_correction"]["status"] == "applied"
    assert data["muf_warning"] is False


# ── Test 2: Storm routing — kp=6 selects PyRayHF ─────────────────────────

def test_storm_routing_rayhf():
    """
    Storm conditions (kp=6) should route to PyRayHF.
    Expects model_used='PyRayHF'.
    """
    storm_payload = {**_BASE_PAYLOAD, "kp": 6.0, "dst": -120.0}

    mock_ssl = MagicMock()
    mock_ssl.transmitter_lat = 25.0
    mock_ssl.transmitter_lon = 74.0
    mock_ssl.ground_distance_km = 200.0
    mock_ssl.virtual_height_km = 350.0
    mock_ssl.model_used = "PyRayHF"
    mock_ssl.selected_model = "PyRayHF"
    mock_ssl.reason = "storm conditions: kp=6.0 >= 5"
    mock_ssl.foF2 = 8.0

    mock_gp_lat = MagicMock()
    mock_gp_lat.predict.return_value = ([0.1], [0.05])
    mock_gp_lat.X_train_ = MagicMock()
    mock_gp_lat.X_train_.shape = (229, 10)

    mock_gp_lon = MagicMock()
    mock_gp_lon.predict.return_value = ([0.08], [0.05])
    mock_gp_lon.X_train_ = MagicMock()
    mock_gp_lon.X_train_.shape = (229, 10)

    with patch("api.main.ssl_locate", return_value=mock_ssl), \
         patch("api.main._gp_lat_sami3", mock_gp_lat), \
         patch("api.main._gp_lon_sami3", mock_gp_lon), \
         patch("api.main._gp_models_loaded", True):

        response = client.post("/locate", json=storm_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["ionosphere"]["model_used"] == "PyRayHF"
    assert data["gp_correction"]["status"] == "applied"


# ── Test 3: IRTAM fallback regression (D1 fix) ───────────────────────────

def test_irtam_fallback_to_iri():
    """
    When IRTAM is selected but unavailable, model_used should be 'IRI'
    and selected_model should be 'IRTAM'. Regression test for D1.
    """
    mock_ssl = MagicMock()
    mock_ssl.transmitter_lat = 24.0
    mock_ssl.transmitter_lon = 73.0
    mock_ssl.ground_distance_km = 170.0
    mock_ssl.virtual_height_km = 290.0
    mock_ssl.model_used = "IRI"           # actual model after fallback
    mock_ssl.selected_model = "IRTAM"     # what was attempted
    mock_ssl.reason = "nominal conditions, IRTAM available"
    mock_ssl.foF2 = 11.0

    with patch("api.main.ssl_locate", return_value=mock_ssl), \
         patch("api.main._gp_models_loaded", True):

        response = client.post("/locate", json=_BASE_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["ionosphere"]["model_used"] == "IRI"
    assert data["ionosphere"]["selected_model"] == "IRTAM"
    # IRI has no GP population — correction should not be applied
    assert data["gp_correction"]["status"] == "not_applied"


# ── Test 4: Elevation guard — elevation_deg=0.5 returns 422 ──────────────

def test_elevation_guard():
    """
    elevation_deg below 1.0 should be rejected with HTTP 422.
    Prevents tan(elevation) singularity.
    """
    bad_payload = {**_BASE_PAYLOAD, "elevation_deg": 0.5}
    response = client.post("/locate", json=bad_payload)
    assert response.status_code == 422


# ── Test 5: OOD month — November returns ood_warning=True ────────────────

def test_ood_month_warning():
    """
    November is outside the training months {6, 7, 12}.
    Expects ood_warning=True in gp_correction.
    """
    nov_payload = {**_BASE_PAYLOAD, "timestamp": "2012-11-15T12:00:00"}

    mock_ssl = MagicMock()
    mock_ssl.transmitter_lat = 24.5
    mock_ssl.transmitter_lon = 73.5
    mock_ssl.ground_distance_km = 180.0
    mock_ssl.virtual_height_km = 280.0
    mock_ssl.model_used = "IRTAM"
    mock_ssl.selected_model = "IRTAM"
    mock_ssl.reason = "nominal conditions, IRTAM available"
    mock_ssl.foF2 = 12.0

    mock_gp_lat = MagicMock()
    mock_gp_lat.predict.return_value = ([0.05], [0.02])
    mock_gp_lat.X_train_ = MagicMock()
    mock_gp_lat.X_train_.shape = (9228, 10)

    mock_gp_lon = MagicMock()
    mock_gp_lon.predict.return_value = ([0.03], [0.02])
    mock_gp_lon.X_train_ = MagicMock()
    mock_gp_lon.X_train_.shape = (9228, 10)

    with patch("api.main.ssl_locate", return_value=mock_ssl), \
         patch("api.main._gp_lat_irtam", mock_gp_lat), \
         patch("api.main._gp_lon_irtam", mock_gp_lon), \
         patch("api.main._gp_models_loaded", True):

        response = client.post("/locate", json=nov_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["gp_correction"]["ood_warning"] is True
