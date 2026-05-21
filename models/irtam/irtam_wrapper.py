"""
PyIRTAM Wrapper — local installation (no HTTP, no CCMC).

Wraps the locally-installed PyIRTAM package (import name: PyIRTAM, case
sensitive) and exposes a profile object compatible with the IRIProfile
contract expected by models/hybrid_model.py.

DRDO Problem ID: DIA-CoE/EW/02
"""

import warnings
import datetime
from dataclasses import dataclass
from typing import Optional

import numpy as np

# PyIRTAM import triggers harmless pandas warnings about numexpr/bottleneck
# versions. Silence them so wrapper output stays clean.
warnings.filterwarnings("ignore", message=".*numexpr.*")
warnings.filterwarnings("ignore", message=".*bottleneck.*")

import PyIRTAM
import PyIRTAM.lib

# ── Configuration constants ──────────────────────────────────────────────
# F10.7 solar flux (SFU). Hardcoded approximation for Solar Cycle 24 peak
# (Ahmedabad 2012). Replace later with a real per-date OMNI value — that is
# a one-line change at the call site since f107 is an optional argument.
DEFAULT_F107 = 130.0

# Vertical altitude grid for the electron density profile, in km.
# 80 km to 1000 km inclusive, 5 km steps.
DEFAULT_ALT_GRID = np.arange(80, 1001, 5)


@dataclass
class IRTAMProfile:
    lat: float
    lon: float
    datetime: datetime.datetime
    NmF2: Optional[float] = None
    hmF2: Optional[float] = None
    foF2: Optional[float] = None
    TEC: Optional[float] = None
    source: str = "PyIRTAM-local"


def _nmf2_to_fof2_mhz(nmf2: float) -> Optional[float]:
    """Convert F2 peak density (m^-3) to critical frequency foF2 (MHz).

    Standard plasma relation: foF2[Hz] = 8.98 * sqrt(Nm[m^-3]).
    """
    if nmf2 is None or nmf2 <= 0:
        return None
    fof2_hz = 8.98 * (nmf2 ** 0.5)
    return round(fof2_hz / 1e6, 4)


def get_irtam_profile(
    lat: float,
    lon: float,
    dt: datetime.datetime,
    f107: float = DEFAULT_F107,
) -> IRTAMProfile:
    """Query the local PyIRTAM model for a single point and time.

    Returns an IRTAMProfile. On ANY failure the numeric fields are left as
    None (the function never raises), so hybrid_model.py can fall back to IRI.
    """
    try:
        # PyIRTAM expects numpy arrays for the spatial/time grids.
        alon = np.array([float(lon)])
        alat = np.array([float(lat)])
        aUT = np.array([dt.hour + dt.minute / 60.0])  # decimal hours
        aalt = DEFAULT_ALT_GRID

        result = PyIRTAM.lib.run_PyIRTAM(
            dt.year,
            dt.month,
            dt.day,
            aUT,
            alon,
            alat,
            aalt,
            float(f107),
            irtam_dir="",      # use package coefficient directory
            use_subdirs=True,
            download=True,     # fetch date-specific IRTAM coefficients
        )

        # run_PyIRTAM returns 12 values; the assimilated PyIRTAM outputs are
        # the *_day entries. We need f2_day.
        # Order: f2_b, f1_b, e_b, es_b, sun, mag, edp_b,
        #        f2_day, f1_day, e_day, es_day, edp_day
        f2_day = result[7]

        nmf2 = float(f2_day["Nm"][0, 0])
        hmf2 = float(f2_day["hm"][0, 0])
        fof2 = _nmf2_to_fof2_mhz(nmf2)

        return IRTAMProfile(
            lat=lat,
            lon=lon,
            datetime=dt,
            NmF2=nmf2,
            hmF2=hmf2,
            foF2=fof2,
            TEC=None,  # run_PyIRTAM does not return a scalar TEC; SSL uses hmF2
            source="PyIRTAM-local",
        )

    except KeyError as e:
        print(f"WARNING: PyIRTAM returned unexpected structure (missing {e}) "
              f"for ({lat}, {lon}, {dt})")
        return IRTAMProfile(lat=lat, lon=lon, datetime=dt)
    except FileNotFoundError as e:
        print(f"WARNING: IRTAM coefficient files unavailable for {dt.date()}: {e}")
        return IRTAMProfile(lat=lat, lon=lon, datetime=dt)
    except Exception as e:
        print(f"WARNING: PyIRTAM query failed for ({lat}, {lon}, {dt}): "
              f"{type(e).__name__}: {e}")
        return IRTAMProfile(lat=lat, lon=lon, datetime=dt)


def is_irtam_available(profile: IRTAMProfile) -> bool:
    """True only if the model produced both foF2 and hmF2."""
    return profile.foF2 is not None and profile.hmF2 is not None


def is_calm_region(kp: float, dst: float) -> bool:
    """Calm geomagnetic conditions test (unchanged from prior contract)."""
    return kp < 3.0 and dst > -50.0


if __name__ == "__main__":
    # Smoke test: Ahmedabad, a 2012 daytime point.
    test_dt = datetime.datetime(2012, 6, 15, 12, 0, 0)
    print(f"Querying local PyIRTAM for Ahmedabad at {test_dt} "
          f"(F10.7={DEFAULT_F107})...\n")
    profile = get_irtam_profile(lat=23.0, lon=72.5, dt=test_dt)
    print("Profile:")
    print(f"  foF2  : {profile.foF2} MHz")
    print(f"  hmF2  : {profile.hmF2} km")
    print(f"  NmF2  : {profile.NmF2} m^-3")
    print(f"  TEC   : {profile.TEC} TECU")
    print(f"  Source: {profile.source}")
    print(f"  Valid : {is_irtam_available(profile)}")
