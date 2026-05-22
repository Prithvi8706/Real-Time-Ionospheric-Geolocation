import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import io
import time
import contextlib
from datetime import datetime
from models.ssl_algorithm import ssl_locate

def main():
    print("Timing 5 ssl_locate calls with irtam_available=True (nominal conditions)...")
    durations = []
    models = []
    for i in range(5):
        t0 = time.time()
        # Suppress the hybrid model's internal prints during the timed call
        with contextlib.redirect_stdout(io.StringIO()):
            result = ssl_locate(
                receiver_lat=22.5,
                receiver_lon=88.3,
                azimuth_deg=45.0,
                elevation_deg=20.0,
                frequency_mhz=10.0,
                dt=datetime(2012, 6, 15, 12, 0, 0),
                kp=2.0,
                dst=-20.0,
                irtam_available=True,
            )
        d = time.time() - t0
        durations.append(d)
        models.append(result.model_used)
        print(f"  call {i+1}: {d:.2f} s  (model_used={result.model_used})")

    avg = sum(durations) / len(durations)
    print(f"\nAverage per call: {avg:.2f} s")
    print(f"Models used: {set(models)}")
    print(f"Estimated full run (9457 rows): {avg * 9457 / 60:.1f} min")
    if "IRTAM" not in models:
        print("WARNING: IRTAM was not selected — check irtam_available wiring before trusting this estimate.")

if __name__ == "__main__":
    main()
