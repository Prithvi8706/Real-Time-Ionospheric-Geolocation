import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from models.ssl_algorithm import ssl_locate

IN_PATH = os.path.join("data", "processed", "ah223_merged_2012_2013.csv")
OUT_PATH = os.path.join("data", "processed", "ssl_real_residuals_2012.csv")

RECEIVER_LAT = 22.5
RECEIVER_LON = 88.3
EARTH_RADIUS_KM = 6371.0
FREQS = [5.0, 10.0, 15.0, 20.0]

def project_location(receiver_lat, receiver_lon, azimuth_deg, ground_distance_km):
    lat1 = np.radians(receiver_lat)
    lon1 = np.radians(receiver_lon)
    az = np.radians(azimuth_deg)
    d = ground_distance_km / EARTH_RADIUS_KM
    lat2 = np.arcsin(
        np.sin(lat1) * np.cos(d) +
        np.cos(lat1) * np.sin(d) * np.cos(az)
    )
    lon2 = lon1 + np.arctan2(
        np.sin(az) * np.sin(d) * np.cos(lat1),
        np.cos(d) - np.sin(lat1) * np.sin(lat2)
    )
    return np.degrees(lat2), np.degrees(lon2)

def haversine_km(lat1, lon1, lat2, lon2):
    R = EARTH_RADIUS_KM
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))

def main():
    df = pd.read_csv(IN_PATH)
    df["dt"] = pd.to_datetime(df["datetime"], utc=True)
    n = len(df)
    print(f"Loaded {n} merged rows", flush=True)

    rng = np.random.default_rng(42)
    azimuths = rng.uniform(0, 360, n)
    distances = rng.uniform(200, 2000, n)
    freqs = rng.choice(FREQS, n)

    rows = []
    attempted = 0
    skipped = 0

    for i in range(n):
        attempted += 1
        try:
            h_true = float(df["hmF2"].iloc[i])
            kp = float(df["kp"].iloc[i])
            dst = float(df["dst"].iloc[i])
            f107 = float(df["f107"].iloc[i])
            dt_py = df["dt"].iloc[i].to_pydatetime()

            az = float(azimuths[i])
            gd = float(distances[i])
            freq = float(freqs[i])

            true_lat, true_lon = project_location(RECEIVER_LAT, RECEIVER_LON, az, gd)
            elevation_deg = np.degrees(np.arctan(h_true / gd))

            result = ssl_locate(
                receiver_lat=RECEIVER_LAT,
                receiver_lon=RECEIVER_LON,
                azimuth_deg=az,
                elevation_deg=elevation_deg,
                frequency_mhz=freq,
                dt=dt_py,
                kp=kp,
                dst=dst,
                irtam_available=True,
            )

            res_lat = true_lat - result.transmitter_lat
            res_lon = true_lon - result.transmitter_lon
            err_km = haversine_km(true_lat, true_lon,
                                  result.transmitter_lat, result.transmitter_lon)

            rows.append({
                "azimuth": az,
                "elevation": elevation_deg,
                "frequency_mhz": freq,
                "dt": df["dt"].iloc[i].isoformat(),
                "kp": kp,
                "dst": dst,
                "f107": f107,
                "virtual_height_km": result.virtual_height_km,
                "hmF2_measured": h_true,
                "baseline_lat": result.transmitter_lat,
                "baseline_lon": result.transmitter_lon,
                "tx_lat": true_lat,
                "tx_lon": true_lon,
                "residual_lat": res_lat,
                "residual_lon": res_lon,
                "error_km": err_km,
                "model_used": result.model_used,
            })
        except Exception as e:
            skipped += 1
            if skipped <= 5:
                print(f"  row {i} skipped: {e}", flush=True)

        if attempted % 1000 == 0:
            print(f"  processed {attempted}/{n} (skipped {skipped})", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_PATH, index=False)

    print(f"\nAttempted : {attempted}", flush=True)
    print(f"Succeeded : {len(out)}", flush=True)
    print(f"Skipped   : {skipped}", flush=True)
    print(f"Saved to {OUT_PATH}", flush=True)
    print(f"\nREAL BASELINE SSL MAE (km): {out['error_km'].mean():.2f}", flush=True)
    print("\nERROR_KM SUMMARY:", flush=True)
    print(out["error_km"].describe().to_string(), flush=True)
    print("\nHEAD:", flush=True)
    print(out.head().to_string(), flush=True)

if __name__ == "__main__":
    main()
