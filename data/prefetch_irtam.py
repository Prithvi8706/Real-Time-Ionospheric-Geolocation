import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import io
import contextlib
import pandas as pd
from models.ssl_algorithm import ssl_locate

IN_PATH = os.path.join("data", "processed", "ah223_merged_2012_2013.csv")

def main():
    df = pd.read_csv(IN_PATH)
    df["dt"] = pd.to_datetime(df["datetime"], utc=True)
    unique_times = sorted(df["dt"].unique())
    n = len(unique_times)
    print(f"Unique timestamps to cache: {n}", flush=True)

    ok = 0
    failed = 0
    failed_list = []

    for i, t in enumerate(unique_times, 1):
        dt_py = pd.Timestamp(t).to_pydatetime()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = ssl_locate(
                    receiver_lat=22.5,
                    receiver_lon=88.3,
                    azimuth_deg=45.0,
                    elevation_deg=20.0,
                    frequency_mhz=10.0,
                    dt=dt_py,
                    kp=2.0,
                    dst=-20.0,
                    irtam_available=True,
                )
            if result.model_used == "IRTAM":
                ok += 1
            else:
                failed += 1
                failed_list.append(str(t))
        except Exception as e:
            failed += 1
            failed_list.append(f"{t} ({e})")

        if i % 100 == 0:
            print(f"  {i}/{n}  cached={ok}  fallback={failed}", flush=True)

    print(f"\nTotal unique timestamps : {n}", flush=True)
    print(f"IRTAM cached OK         : {ok}", flush=True)
    print(f"Fell back to IRI        : {failed}", flush=True)
    if failed_list:
        print("\nFirst failures (retry these):", flush=True)
        for f in failed_list[:20]:
            print(f"  {f}", flush=True)

if __name__ == "__main__":
    main()
