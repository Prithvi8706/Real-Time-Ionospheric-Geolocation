"""
IRI (International Reference Ionosphere) Wrapper
Used as fallback model for calm ionospheric regions.
Part of the hybrid ionospheric model for DRDO DIA-CoE/EW/02.
"""

import numpy as np
import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class IRIProfile:
    """Stores IRI model output for a given location and time."""
    lat: float
    lon: float
    datetime: datetime.datetime
    NmF2: Optional[float] = None       # Peak electron density (m^-3)
    hmF2: Optional[float] = None       # Peak height (km)
    foF2: Optional[float] = None       # Critical frequency (MHz)
    TEC: Optional[float] = None        # Total Electron Content (TECU)
    source: str = "IRI"

def get_iri_profile(lat: float, lon: float, dt: datetime.datetime) -> IRIProfile:
    """
    Query IRI model for ionospheric parameters at given location and time.

    Args:
        lat: Latitude in degrees (N positive)
        lon: Longitude in degrees (E positive)
        dt: Datetime (UTC)

    Returns:
        IRIProfile dataclass with predicted ionospheric parameters.
        Returns a null profile (all None fields) if IRI data is unavailable
        or out of the model's valid date range (approximately 1958–2020).
    """
    try:
        from iri2016 import IRI

        result = IRI(dt, [100, 500, 10], lat, lon)

        # Use IRI's own scalar outputs — more accurate than recomputing from ne.
        hmF2 = float(result['hmF2'].values)

        # IRI uses -1.0 as a sentinel when the requested date is outside its
        # coverage (typically years >= 2021 for the bundled coefficient files).
        if hmF2 <= 0:
            print(
                f"WARNING: IRI returned invalid hmF2={hmF2} for "
                f"({lat}, {lon}, {dt}) — date likely outside IRI coverage "
                f"(model valid ~1958–2020). Returning null profile."
            )
            return IRIProfile(lat=lat, lon=lon, datetime=dt)

        NmF2 = float(result['NmF2'].values)
        foF2 = float(result['foF2'].values)
        TEC  = float(result['TEC'].values)

        return IRIProfile(
            lat=lat, lon=lon, datetime=dt,
            NmF2=NmF2, hmF2=hmF2, foF2=foF2, TEC=TEC
        )

    except ImportError:
        print("WARNING: iri2016 not installed.")
        return IRIProfile(lat=lat, lon=lon, datetime=dt)

    except Exception as e:
        print(f"WARNING: IRI query failed for ({lat}, {lon}, {dt}): {e}")
        return IRIProfile(lat=lat, lon=lon, datetime=dt)


def is_calm_region(kp: float, dst: float) -> bool:
    """
    Determine if ionospheric conditions are calm enough to use IRI as fallback.

    Args:
        kp: Kp geomagnetic index (0-9)
        dst: Dst storm index (nT)

    Returns:
        True if conditions are calm (IRI is reliable)
    """
    return kp < 3.0 and dst > -50.0


if __name__ == "__main__":
    # Quick test
    test_dt = datetime.datetime(2015, 1, 1, 12, 0, 0)
    profile = get_iri_profile(lat=22.58, lon=88.37, dt=test_dt)
    print(f"IRI Profile for Calcutta at {test_dt}:")
    print(f"  NmF2 : {profile.NmF2}")
    print(f"  hmF2 : {profile.hmF2} km")
    print(f"  foF2 : {profile.foF2} MHz")
    print(f"  TEC  : {profile.TEC} TECU")
    print(f"  Source: {profile.source}")
