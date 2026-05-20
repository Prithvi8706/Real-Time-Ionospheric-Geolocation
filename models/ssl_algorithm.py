import numpy as np
from dataclasses import dataclass
from datetime import datetime
from models.hybrid_model import get_ionosphere

EARTH_RADIUS_KM = 6371.0

@dataclass
class SSLResult:
    transmitter_lat: float
    transmitter_lon: float
    ground_distance_km: float
    virtual_height_km: float
    model_used: str
    reason: str

def compute_ground_distance(virtual_height_km: float, elevation_deg: float) -> float:
    """
    Classical SSL geometry:
    ground_distance = virtual_height / tan(elevation)
    """
    elevation_rad = np.radians(elevation_deg)
    return virtual_height_km / np.tan(elevation_rad)

def compute_transmitter_location(
    receiver_lat: float,
    receiver_lon: float,
    azimuth_deg: float,
    ground_distance_km: float
) -> tuple[float, float]:
    """
    Move from receiver along azimuth by ground_distance.
    Uses spherical Earth geometry.
    """
    lat1 = np.radians(receiver_lat)
    lon1 = np.radians(receiver_lon)
    az   = np.radians(azimuth_deg)
    d    = ground_distance_km / EARTH_RADIUS_KM  # angular distance

    lat2 = np.arcsin(
        np.sin(lat1) * np.cos(d) +
        np.cos(lat1) * np.sin(d) * np.cos(az)
    )
    lon2 = lon1 + np.arctan2(
        np.sin(az) * np.sin(d) * np.cos(lat1),
        np.cos(d) - np.sin(lat1) * np.sin(lat2)
    )

    return np.degrees(lat2), np.degrees(lon2)

def ssl_locate(
    receiver_lat: float,
    receiver_lon: float,
    azimuth_deg: float,
    elevation_deg: float,
    frequency_mhz: float,
    dt: datetime,
    kp: float,
    dst: float,
    irtam_available: bool = False
) -> SSLResult:
    """
    Full SSL pipeline:
      1. Get ionospheric profile from hybrid model
      2. Use hmF2 as virtual height
      3. Compute ground distance via geometry
      4. Project along azimuth to get transmitter location
    """

    # Step 1a: Initial rough transmitter estimate using receiver location
    iono_init = get_ionosphere(
        lat=receiver_lat,
        lon=receiver_lon,
        dt=dt,
        kp=kp,
        dst=dst,
        irtam_available=irtam_available
    )
    rough_height = iono_init["profile"].hmF2
    rough_distance = compute_ground_distance(rough_height, elevation_deg)
    rough_tx_lat, rough_tx_lon = compute_transmitter_location(
        receiver_lat, receiver_lon,
        azimuth_deg, rough_distance
    )

    # Step 1b: Compute midpoint between receiver and rough transmitter
    mid_lat = (receiver_lat + rough_tx_lat) / 2
    mid_lon = (receiver_lon + rough_tx_lon) / 2

    # Step 1c: Re-query ionosphere at midpoint (bounce point)
    iono = get_ionosphere(
        lat=mid_lat,
        lon=mid_lon,
        dt=dt,
        kp=kp,
        dst=dst,
        irtam_available=irtam_available
    )
    virtual_height_km = iono["profile"].hmF2

    # Step 2: Ground distance
    ground_distance_km = compute_ground_distance(virtual_height_km, elevation_deg)

    # Step 3: Transmitter location
    tx_lat, tx_lon = compute_transmitter_location(
        receiver_lat, receiver_lon,
        azimuth_deg, ground_distance_km
    )

    return SSLResult(
        transmitter_lat=round(tx_lat, 4),
        transmitter_lon=round(tx_lon, 4),
        ground_distance_km=round(ground_distance_km, 2),
        virtual_height_km=round(virtual_height_km, 2),
        model_used=iono["model_used"],
        reason=iono["reason"]
    )
