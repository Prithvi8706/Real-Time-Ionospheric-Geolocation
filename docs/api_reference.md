# API Reference — Real-Time Ionospheric Geolocation

**Service:** Real-Time Ionospheric Geolocation  
**Version:** 1.0.0  
**Problem ID:** DRDO DIA-CoE/EW/02  
**Base URL (local):** `http://127.0.0.1:8000`

---

## Endpoints

### `GET /`

Returns the Leaflet dark ops-console UI as an HTML page.

Static assets (Leaflet CSS, Leaflet JS, map tile stubs) are served from
`api/static/` — no CDN or internet dependency for the UI shell. Map tile
imagery from OpenStreetMap still requires internet unless a local tile
server is configured.

**Response:** `200 OK`, `Content-Type: text/html`

---

### `GET /health`

Service health check. Confirms the GP models loaded correctly and reports
training row counts for pre-demo verification.

**Response body (JSON):**

```json
{
  "status": "ok",
  "gp_models_loaded": true,
  "gp_models": {
    "irtam": true,
    "sami3": true
  },
  "gp_training_rows": {
    "irtam": 7382,
    "sami3": 183
  }
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"ok"` if the service is running |
| `gp_models_loaded` | bool | `true` if all four GP `.pkl` files loaded at startup |
| `gp_models.irtam` | bool | Both `gp_lat_irtam.pkl` and `gp_lon_irtam.pkl` loaded |
| `gp_models.sami3` | bool | Both `gp_lat_sami3.pkl` and `gp_lon_sami3.pkl` loaded |
| `gp_training_rows.irtam` | int | Training set size for the IRTAM GP (expected: 7382) |
| `gp_training_rows.sami3` | int | Training set size for the PyRayHF/storm GP (expected: 183) |

If `gp_models_loaded` is `false`, all `/locate` responses will return
`gp_correction.status = "unavailable"`. The SSL physics estimate is still
produced.

---

### `POST /locate`

Primary endpoint. Runs the full SSL geolocation pipeline and returns a
transmitter location estimate with optional GP correction.

#### Request schema

```json
{
  "receiver_lat":    23.0,
  "receiver_lon":    72.0,
  "azimuth_deg":     45.0,
  "elevation_deg":   15.0,
  "frequency_mhz":   10.0,
  "timestamp":       "2012-06-15T12:00:00",
  "kp":              1.0,
  "dst":             -10.0,
  "f107":            130.0,
  "irtam_available": true
}
```

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `receiver_lat` | float | yes | −90 to 90 | Receiver latitude, degrees N |
| `receiver_lon` | float | yes | −180 to 180 | Receiver longitude, degrees E |
| `azimuth_deg` | float | yes | 0 to 360 | Bearing from receiver to emitter, degrees true north |
| `elevation_deg` | float | yes | 1.0 to 60.0 | Elevation angle of the arriving signal. Below 1° risks `tan(elevation)` singularity; above 60° is outside typical HF skywave geometry |
| `frequency_mhz` | float | yes | 2 to 30 | Signal frequency in MHz (HF band) |
| `timestamp` | string | yes | ISO 8601 | UTC time of observation, e.g. `"2012-06-15T12:00:00"` |
| `kp` | float | yes | 0 to 9 | Kp geomagnetic index at observation time |
| `dst` | float | yes | −500 to 50 | Dst ring-current index, nT. Negative values indicate storm activity |
| `f107` | float | no | 50 to 300, default 130.0 | Solar flux index (SFU) at 10.7 cm. Defaults to 130.0 SFU, the approximate Solar Cycle 24 peak value used during training. Must be a finite number |
| `irtam_available` | bool | no | default `false` | Set `true` when local PyIRTAM coefficient files for the requested date are installed. If `false`, IRTAM is bypassed and IRI is used for nominal conditions |

**Validation errors** return `422 Unprocessable Entity` with a Pydantic
error body listing every field that failed validation.

#### Response schema

```json
{
  "primary_estimate": {
    "transmitter_lat": 24.5,
    "transmitter_lon": 73.5,
    "ground_distance_km": 180.0,
    "virtual_height_km": 280.0,
    "method": "SSL physics (hybrid ionospheric model)"
  },
  "ionosphere": {
    "model_used": "IRTAM",
    "selected_model": "IRTAM",
    "reason": "IRTAM available and conditions are nominal"
  },
  "gp_correction": {
    "status": "applied",
    "note": "GP correction applied (IRTAM population). ...",
    "corrected_lat": 24.55,
    "corrected_lon": 73.53,
    "uncertainty_lat_deg": 0.02,
    "uncertainty_lon_deg": 0.02,
    "ood_warning": false,
    "correction_std_km": 3.14
  },
  "muf_warning": false
}
```

##### `primary_estimate` object

| Field | Type | Description |
|---|---|---|
| `transmitter_lat` | float | SSL physics estimate of emitter latitude, degrees N (4 d.p.) |
| `transmitter_lon` | float | SSL physics estimate of emitter longitude, degrees E (4 d.p.) |
| `ground_distance_km` | float | Estimated ground range from receiver to emitter (km, 2 d.p.) |
| `virtual_height_km` | float | Virtual height used in the SSL calculation (km, 2 d.p.). Ray-traced for PyRayHF; `hmF2` for all other models |
| `method` | string | Always `"SSL physics (hybrid ionospheric model)"` |

##### `ionosphere` object

| Field | Type | Description |
|---|---|---|
| `model_used` | string | Ionospheric model that actually produced the profile. One of: `"IRTAM"`, `"IRI"`, `"A-CHAIM"`, `"PyRayHF"`. May differ from `selected_model` when a fallback occurred (D1 audit trail) |
| `selected_model` | string | Model that the selector attempted. Records the original intent before any runtime fallback |
| `reason` | string | Human-readable explanation of why this model was selected |

The distinction between `model_used` and `selected_model` matters for the
GP correction layer: the GP routes on `model_used`, not `selected_model`.
See the Architecture document for details.

##### `gp_correction` object

| Field | Type | Description |
|---|---|---|
| `status` | string | One of: `"applied"`, `"not_applied"`, `"unavailable"`, `"prediction_failed"` |
| `note` | string | Explanation of the GP status, including training scope and OOD warnings if triggered |
| `corrected_lat` | float \| null | GP-corrected emitter latitude. `null` if correction not applied |
| `corrected_lon` | float \| null | GP-corrected emitter longitude. `null` if correction not applied |
| `uncertainty_lat_deg` | float \| null | GP posterior standard deviation for latitude residual, in degrees |
| `uncertainty_lon_deg` | float \| null | GP posterior standard deviation for longitude residual, in degrees |
| `ood_warning` | bool | `true` if the request falls outside the GP training distribution (month not in {June, July, December} or transmitter latitude outside 15°N–35°N) |
| `correction_std_km` | float \| null | RSS of lat and lon uncertainties converted to km, accounting for `cos(lat)` scaling on longitude. Formula: `sqrt((std_lat × 111)² + (std_lon × 111 × cos(lat))²)` |

**GP status values:**

| `status` | Meaning |
|---|---|
| `"applied"` | GP predicted residuals and corrected the estimate |
| `"not_applied"` | No GP population exists for this model branch (IRI or A-CHAIM) |
| `"unavailable"` | GP model files could not be loaded at service startup |
| `"prediction_failed"` | GP files loaded but an internal error occurred during prediction |

##### `muf_warning` field

| Field | Type | Description |
|---|---|---|
| `muf_warning` | bool | `true` if `frequency_mhz` exceeds `foF2` from the ionospheric model. When true, the signal may penetrate the ionosphere rather than reflect; the SSL estimate should be treated as unreliable |

#### HTTP error codes

| Code | Condition |
|---|---|
| `200 OK` | Request processed successfully |
| `422 Unprocessable Entity` | One or more request fields failed validation. Body contains Pydantic error details identifying each failing field |
| `503 Service Unavailable` | Ionospheric model returned a null or non-positive virtual height. This can occur if PyIRTAM coefficient files are missing for the requested date and IRI also fails |

---

## Feature vector (GP models)

The ten features fed to each GP model, in order:

```
[azimuth_deg, elevation_deg, frequency_mhz, virtual_height_km,
 kp, dst, hour, month, baseline_lat, baseline_lon]
```

`baseline_lat` and `baseline_lon` are the SSL physics estimate
(`transmitter_lat`, `transmitter_lon` from `primary_estimate`).
`hour` and `month` are extracted from `timestamp`.
