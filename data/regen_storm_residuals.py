"""
Regenerate ONLY the storm-condition residual rows after the D8 fix
(PyRayHF now ray-traces at the request frequency instead of fixed 5 MHz).

Deterministic replay: the original data/generate_real_residuals.py drew
azimuth/distance/frequency for all n rows up front with seed 42 and had
zero skipped rows, so merged row i <-> residual row i. Each replayed draw
is asserted against the old CSV's azimuth before the row is replaced.

IRTAM rows are untouched — D8 only affects the PyRayHF branch.

Run from repo root:
    python data/regen_storm_residuals.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from models.ssl_algorithm import ssl_locate
from data.generate_real_residuals import (
    IN_PATH, OUT_PATH, RECEIVER_LAT, RECEIVER_LON, FREQS,
    project_location, haversine_km,
)


def main():
    merged = pd.read_csv(IN_PATH)
    merged["dt"] = pd.to_datetime(merged["datetime"], utc=True)
    residuals = pd.read_csv(OUT_PATH)
    n = len(merged)
    assert len(residuals) == n, "merged and residual CSVs must be index-aligned"

    rng = np.random.default_rng(42)
    azimuths = rng.uniform(0, 360, n)
    distances = rng.uniform(200, 2000, n)
    freqs = rng.choice(FREQS, n)

    storm = ((merged["kp"] >= 5) | (merged["dst"] <= -100)).values
    idx = np.where(storm)[0]
    print(f"Regenerating {len(idx)} storm-condition rows of {n}", flush=True)

    replaced = 0
    for i in idx:
        az = float(azimuths[i])
        # alignment guard: replayed draw must match the original row
        assert abs(residuals.at[i, "azimuth"] - az) < 1e-9, f"row {i} misaligned"

        h_true = float(merged["hmF2"].iloc[i])
        gd = float(distances[i])
        freq = float(freqs[i])
        true_lat, true_lon = project_location(RECEIVER_LAT, RECEIVER_LON, az, gd)
        elevation_deg = float(np.degrees(np.arctan(h_true / gd)))

        result = ssl_locate(
            receiver_lat=RECEIVER_LAT, receiver_lon=RECEIVER_LON,
            azimuth_deg=az, elevation_deg=elevation_deg,
            frequency_mhz=freq, dt=merged["dt"].iloc[i].to_pydatetime(),
            kp=float(merged["kp"].iloc[i]), dst=float(merged["dst"].iloc[i]),
            irtam_available=True,
        )

        residuals.at[i, "virtual_height_km"] = result.virtual_height_km
        residuals.at[i, "baseline_lat"] = result.transmitter_lat
        residuals.at[i, "baseline_lon"] = result.transmitter_lon
        residuals.at[i, "residual_lat"] = true_lat - result.transmitter_lat
        residuals.at[i, "residual_lon"] = true_lon - result.transmitter_lon
        residuals.at[i, "error_km"] = float(haversine_km(
            true_lat, true_lon, result.transmitter_lat, result.transmitter_lon))
        residuals.at[i, "model_used"] = result.model_used
        replaced += 1
        if replaced % 25 == 0:
            print(f"  {replaced}/{len(idx)}", flush=True)

    residuals.to_csv(OUT_PATH, index=False)
    print(f"\nReplaced {replaced} rows -> {OUT_PATH}", flush=True)
    print("New model_used counts:", flush=True)
    print(residuals["model_used"].value_counts().to_string(), flush=True)
    storm_rows = residuals[storm]
    print(f"\nStorm-condition baseline MAE now: {storm_rows['error_km'].mean():.2f} km",
          flush=True)


if __name__ == "__main__":
    main()
