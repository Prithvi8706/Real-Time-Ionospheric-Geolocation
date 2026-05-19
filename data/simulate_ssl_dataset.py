import sys
sys.path.insert(0, '..')

import numpy as np
import pandas as pd
from datetime import datetime
from models.ssl_algorithm import ssl_locate

# Calcutta receiver
RECEIVER_LAT = 22.5
RECEIVER_LON = 88.3

# Simulation grid
azimuths   = np.arange(0, 360, 30)       # 12 directions
elevations = np.arange(5, 45, 5)         # 8 elevation angles
frequencies = [5.0, 10.0, 15.0, 20.0]   # 4 HF frequencies (MHz)
dt = datetime(2020, 6, 15, 12, 0, 0)
kp, dst = 1.0, -20.0

rows = []
for az in azimuths:
    for el in elevations:
        for freq in frequencies:
            result = ssl_locate(
                receiver_lat=RECEIVER_LAT,
                receiver_lon=RECEIVER_LON,
                azimuth_deg=az,
                elevation_deg=el,
                frequency_mhz=freq,
                dt=dt,
                kp=kp,
                dst=dst,
                irtam_available=False
            )
            rows.append({
                "azimuth":            az,
                "elevation":          el,
                "frequency_mhz":      freq,
                "virtual_height_km":  result.virtual_height_km,
                "ground_distance_km": result.ground_distance_km,
                "tx_lat":             result.transmitter_lat,
                "tx_lon":             result.transmitter_lon,
                "model_used":         result.model_used
            })

df = pd.DataFrame(rows)
df.to_csv("data/processed/ssl_simulated_dataset.csv", index=False)
print(f"Saved {len(df)} rows to data/processed/ssl_simulated_dataset.csv")
print(df.head(10).to_string())
