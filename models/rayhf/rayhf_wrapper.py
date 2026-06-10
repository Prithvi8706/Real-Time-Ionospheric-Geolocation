"""
PyRayHF Virtual Height Wrapper
Used for storm-time rows (kp >= 5 or dst <= -100) in the hybrid model.
Replaces the empty SAMI3 placeholder for the DRDO DIA-CoE/EW/02 system.

Physics:
    virtual_height = find_vh(X, Y, bpsi, dh, alt_min, mode="O")
    X[i]    = Ne[i] * 80.6 / f_Hz^2          (plasma freq ratio squared)
    Y[i]    = fH[i] / f_MHz                   (gyrofreq ratio)
    fH[i]   = 28e3 * mag_T[i]                 (gyrofrequency in MHz; mag in Tesla)
    bpsi[i] = psi[i]                          (B angle from vertical, degrees)
    dh      = 10 km uniform (IRI grid 100-500 km, step 10)
    alt_min = 100 km

Ionosonde frequency: 5.0 MHz (representative mid-HF for low-latitude solar max)

API shape convention (learned empirically):
    calculate_magnetic_field: lat/lon must be arrays of shape (n_alts,); returns (n_alts, n_alts)
    find_vh: all array inputs must be 2D (n_alts, 1); returns (n_alts, 1) — squeeze to (n_alts,)
    find_vh output: cumulative virtual height per layer; nan once ray has reflected.
                    Correct value = last non-nan entry (the reflection point).
    Units: calculate_magnetic_field returns mag in Tesla (not nT despite docstring)
"""

import numpy as np
import datetime
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Ionosonde frequency used for X and Y calculations
_F_MHZ = 5.0
_F_HZ = _F_MHZ * 1e6

# IRI altitude grid parameters (must match iri_wrapper.py call: [100, 500, 10])
_ALT_MIN_KM = 100.0
_ALT_MAX_KM = 500.0
_ALT_STEP_KM = 10.0
_DH = _ALT_STEP_KM


@dataclass
class RayHFProfile:
    """Stores PyRayHF output for a given location and time."""
    lat: float
    lon: float
    datetime: datetime.datetime
    virtual_height_km: Optional[float] = None
    hmF2: Optional[float] = None        # kept for interface compatibility with hybrid_model
    foF2: Optional[float] = None        # kept for interface compatibility
    NmF2: Optional[float] = None        # kept for interface compatibility
    source: str = "PyRayHF"


def get_rayhf_profile(lat: float, lon: float, dt: datetime.datetime) -> RayHFProfile:
    """
    Compute virtual height via PyRayHF ray tracing for a given location and time.

    Uses IRI electron density profile as input to the ray tracer.
    Intended for storm-time rows only (kp >= 5 or dst <= -100).

    **Frequency assumption (D8):** PyRayHF is calibrated at _F_MHZ=5.0 MHz,
    representative of AH223 solar max conditions. Storm GP models
    (gp_lat_sami3.pkl, gp_lon_sami3.pkl) were trained at this frequency.
    Passing arbitrary request.frequency_mhz into the GP feature vector while
    physics runs at 5 MHz is a known limitation — see TODOS.md.

    Args:
        lat: Latitude in degrees (N positive)
        lon: Longitude in degrees (E positive)
        dt: Datetime (UTC, timezone-aware or naive)

    Returns:
        RayHFProfile with virtual_height_km set if successful, None fields otherwise.
    """
    try:
        import PyRayHF.library as rayhf
        from iri2016 import IRI

        # --- Step 1: IRI electron density profile ---
        alts = np.arange(_ALT_MIN_KM, _ALT_MAX_KM + _ALT_STEP_KM, _ALT_STEP_KM)
        result = IRI(dt, [int(_ALT_MIN_KM), int(_ALT_MAX_KM), int(_ALT_STEP_KM)], lat, lon)
        ne = result['ne'].values  # shape (N,), m^-3

        # Guard: IRI occasionally returns all-NaN profiles
        if np.all(np.isnan(ne)):
            logger.warning(f"PyRayHF: IRI returned all-NaN Ne for ({lat}, {lon}, {dt})")
            return RayHFProfile(lat=lat, lon=lon, datetime=dt)

        ne = np.nan_to_num(ne, nan=0.0)  # NaN layers → 0 (no plasma)

        # --- Step 2: Magnetic field profile ---
        # calculate_magnetic_field requires array lat/lon of same length as alts.
        # Returns (n_alts, n_alts) matrix; take column 0 (all identical for single point).
        # Units: mag in Tesla (not nT despite docstring).
        lat_arr = np.full(len(alts), lat)
        lon_arr = np.full(len(alts), lon)
        mag_2d, psi_2d = rayhf.calculate_magnetic_field(
            dt.year, dt.month, dt.day,
            lat_arr, lon_arr,
            alts
        )
        mag = np.asarray(mag_2d)[:, 0]   # shape (41,), Tesla
        psi = np.asarray(psi_2d)[:, 0]   # shape (41,), degrees from vertical

        # --- Step 3: Assemble find_vh inputs ---
        # find_vh expects 2D inputs of shape (n_alts, 1).

        # X = (fp/f)^2 = Ne * 80.6 / f_Hz^2
        X = (ne * 80.6 / (_F_HZ ** 2)).reshape(-1, 1)

        # Y = fH / f_MHz, where fH = 28e3 * mag_T (MHz)
        fH = 28e3 * mag   # MHz
        Y = (fH / _F_MHZ).reshape(-1, 1)

        # bpsi = angle between wave vector and B (vertical wave = psi from vertical)
        bpsi = psi.reshape(-1, 1)

        # dh: uniform layer thickness (km), shape (n_alts, 1)
        dh = np.full((len(alts), 1), _DH)

        # --- Step 4: Compute virtual height ---
        vh_2d = rayhf.find_vh(X, Y, bpsi, dh, _ALT_MIN_KM, "O")
        vh_arr = np.asarray(vh_2d).squeeze()  # shape (41,)

        # find_vh returns cumulative virtual height per layer; nan once the ray has
        # reflected. The correct virtual height is the last non-nan value — the
        # reflection point. Taking peak_idx (F2 peak) would always land in the nan
        # region because reflection occurs before the Ne maximum.
        valid_mask = ~np.isnan(vh_arr)
        if not np.any(valid_mask):
            logger.warning(f"PyRayHF: find_vh returned all-nan for ({lat}, {lon}, {dt})")
            return RayHFProfile(lat=lat, lon=lon, datetime=dt)

        virtual_height_km = float(vh_arr[valid_mask][-1])  # last non-nan = reflection point

        # Sanity check: virtual height must be physically reasonable
        if not (50.0 < virtual_height_km < 1000.0):
            logger.warning(
                f"PyRayHF: unrealistic vh={virtual_height_km:.1f} km for "
                f"({lat}, {lon}, {dt}) — returning None"
            )
            return RayHFProfile(lat=lat, lon=lon, datetime=dt)

        # Derive hmF2 and foF2 from IRI profile for interface compatibility
        peak_idx = int(np.nanargmax(ne))
        hmF2 = float(alts[peak_idx])
        NmF2 = float(ne[peak_idx])
        foF2 = float(8.98e-6 * np.sqrt(NmF2)) if NmF2 > 0 else None

        return RayHFProfile(
            lat=lat, lon=lon, datetime=dt,
            virtual_height_km=virtual_height_km,
            hmF2=hmF2,
            foF2=foF2,
            NmF2=NmF2,
        )

    except ImportError as e:
        logger.error(f"PyRayHF import failed: {e}")
        return RayHFProfile(lat=lat, lon=lon, datetime=dt)

    except Exception as e:
        logger.warning(f"PyRayHF query failed for ({lat}, {lon}, {dt}): {e}")
        return RayHFProfile(lat=lat, lon=lon, datetime=dt)


def is_rayhf_available(profile: RayHFProfile) -> bool:
    """Return True only if the profile contains a usable virtual height."""
    return (
        profile.virtual_height_km is not None
        and not np.isnan(profile.virtual_height_km)
    )


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")

    test_dt = datetime.datetime(2012, 7, 15, 6, 0, 0)
    print(f"PyRayHF smoke test: ({23.0}, {72.6}, {test_dt})")
    profile = get_rayhf_profile(lat=23.0, lon=72.6, dt=test_dt)
    print(f"  virtual_height_km : {profile.virtual_height_km}")
    print(f"  hmF2              : {profile.hmF2} km")
    print(f"  foF2              : {profile.foF2} MHz")
    print(f"  NmF2              : {profile.NmF2} m^-3")
    print(f"  Valid             : {is_rayhf_available(profile)}")
    print(f"  Source            : {profile.source}")