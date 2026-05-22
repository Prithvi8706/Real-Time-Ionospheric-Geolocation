import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import time
from datetime import datetime
from models.ssl_algorithm import ssl_locate

def main():
    print("Timing 5 single ssl_locate calls...")
    durations = []
    for i in range(5):
        t0 = time.time()
        result = ssl_locate(
            receiver_lat=22.5,
            receiver_lon=88.3,
            azimuth_deg=45.0,
            elevation_deg=20.0,
            frequency_mhz=10.0,
            dt=datetime(2012, 6, 15, 12, 0, 0),
            kp=2.0,
            dst=-20.0,
            irtam_available=False,
        )
        dt = time.time() - t0
        durations.append(dt)
        print(f"  call {i+1}: {dt:.2f} s  (model_used={result.model_used})")

    avg = sum(durations) / len(durations)
    print(f"\nAverage per call: {avg:.2f} s")
    print(f"Estimated full run (9457 rows): {avg * 9457 / 60:.1f} min")

if __name__ == "__main__":
    main()
