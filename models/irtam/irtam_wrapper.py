"""
IRTAM/IRI Wrapper using CCMC NASA REST API
No local installation needed — pure HTTP requests.
DRDO Problem ID: DIA-CoE/EW/02
"""

import requests
import datetime
from dataclasses import dataclass
from typing import Optional

CCMC_URL = "https://kauai.ccmc.gsfc.nasa.gov/instantrun/iri2016"

@dataclass
class IRTAMProfile:
    lat: float
    lon: float
    datetime: datetime.datetime
    NmF2: Optional[float] = None
    hmF2: Optional[float] = None
    foF2: Optional[float] = None
    TEC:  Optional[float] = None
    source: str = "IRI2016-CCMC"


def get_irtam_profile(lat: float, lon: float, dt: datetime.datetime) -> IRTAMProfile:
    try:
        params = {
            "lat":   lat,
            "lon":   lon,
            "year":  dt.year,
            "month": dt.month,
            "day":   dt.day,
            "hour":  dt.hour + dt.minute / 60.0,
        }

        response = requests.get(CCMC_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        foF2 = data.get("foF2", None)
        hmF2 = data.get("hmF2", None)
        NmF2 = (float(foF2) / 8.98e-3) ** 2 if foF2 else None
        TEC  = data.get("TEC", None)

        return IRTAMProfile(
            lat=lat, lon=lon, datetime=dt,
            NmF2=NmF2,
            hmF2=float(hmF2) if hmF2 else None,
            foF2=float(foF2) if foF2 else None,
            TEC=float(TEC) if TEC else None
        )

    except requests.exceptions.Timeout:
        print(f"WARNING: CCMC API timed out")
        return IRTAMProfile(lat=lat, lon=lon, datetime=dt)

    except requests.exceptions.ConnectionError:
        print(f"WARNING: Could not connect to CCMC API")
        return IRTAMProfile(lat=lat, lon=lon, datetime=dt)

    except Exception as e:
        print(f"WARNING: IRI query failed for ({lat}, {lon}, {dt}): {e}")
        return IRTAMProfile(lat=lat, lon=lon, datetime=dt)


def is_irtam_available(profile: IRTAMProfile) -> bool:
    return profile.foF2 is not None and profile.hmF2 is not None


def is_calm_region(kp: float, dst: float) -> bool:
    return kp < 3.0 and dst > -50.0


if __name__ == "__main__":
    test_dt = datetime.datetime(2020, 6, 15, 12, 0, 0)
    print(f"Querying IRI2016 via CCMC for Calcutta at {test_dt}...\n")
    profile = get_irtam_profile(lat=22.58, lon=88.37, dt=test_dt)
    print(f"Profile:")
    print(f"  foF2  : {profile.foF2} MHz")
    print(f"  hmF2  : {profile.hmF2} km")
    print(f"  NmF2  : {profile.NmF2}")
    print(f"  TEC   : {profile.TEC} TECU")
    print(f"  Source: {profile.source}")
    print(f"  Valid : {is_irtam_available(profile)}")
