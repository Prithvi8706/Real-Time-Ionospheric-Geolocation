import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models.ssl_algorithm import ssl_locate

def main():
    print("Probing GIRO server with an UNCACHED date (2012-06-13 15:45)...")
    print("Watch for: 503 errors / 'Bad IRTAM coefficient query' / 'falling back to IRI'")
    print("-" * 60)
    result = ssl_locate(
        receiver_lat=22.5,
        receiver_lon=88.3,
        azimuth_deg=45.0,
        elevation_deg=20.0,
        frequency_mhz=10.0,
        dt=datetime(2012, 6, 13, 15, 45, 0),
        kp=2.0,
        dst=-20.0,
        irtam_available=True,
    )
    print("-" * 60)
    print(f"RESULT model_used = {result.model_used}")
    if result.model_used == "IRTAM":
        print("=> SERVER IS BACK. IRTAM fetched the uncached date successfully.")
    else:
        print(f"=> SERVER STILL DOWN or unreachable. Fell back to {result.model_used}.")

if __name__ == "__main__":
    main()
