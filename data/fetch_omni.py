import os
import io
import urllib.request
import pandas as pd
import numpy as np

OUT_DIR = os.path.join("data", "processed")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, "omni_indices_2012_2013.csv")

# OMNI2 hourly ASCII: yearly files. Columns are fixed by OMNI2 format.
# Format reference (selected fields, 1-indexed in OMNI docs):
#   col 1: year, col 2: day-of-year, col 3: hour,
#   Kp index stored as Kp*10 (integer), Dst (nT), F10.7 (daily, sfu).
# We use the per-year omni2_YYYY.dat files.
BASE = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_{year}.dat"

def fetch_year(year):
    url = BASE.format(year=year)
    print(f"Fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("ascii", errors="replace")
    return raw

def parse_omni2(raw):
    # OMNI2 hourly .dat is whitespace-delimited fixed columns.
    # Field positions (0-indexed) in omni2 hourly format:
    #   0 year, 1 doy, 2 hour, ... 38 Kp(*10), 40 Dst, 50 F10.7
    # These indices follow the standard omni2.text format definition.
    records = []
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 55:
            continue
        try:
            year = int(parts[0])
            doy = int(parts[1])
            hour = int(parts[2])
            kp_raw = int(parts[38])
            dst = int(parts[40])
            f107 = float(parts[50])
        except (ValueError, IndexError):
            continue
        records.append((year, doy, hour, kp_raw, dst, f107))
    return records

def main():
    all_records = []
    for year in (2012, 2013):
        raw = fetch_year(year)
        recs = parse_omni2(raw)
        print(f"  {year}: parsed {len(recs)} rows")
        all_records.extend(recs)

    if not all_records:
        raise RuntimeError("No OMNI rows parsed — check format/positions before proceeding.")

    df = pd.DataFrame(all_records, columns=["year", "doy", "hour", "kp_raw", "dst", "f107"])

    # Build UTC datetime from year + day-of-year + hour
    df["datetime"] = (
        pd.to_datetime(df["year"].astype(str) + df["doy"].astype(str).str.zfill(3), format="%Y%j", utc=True)
        + pd.to_timedelta(df["hour"], unit="h")
    )

    # Kp stored as Kp*10
    df["kp"] = df["kp_raw"] / 10.0

    # Drop OMNI fill values
    df = df[df["dst"] != 9999]
    df = df[df["f107"] < 999.0]

    out = df[["datetime", "kp", "dst", "f107"]].sort_values("datetime").reset_index(drop=True)
    out.to_csv(OUT_PATH, index=False)

    print(f"\nSaved {len(out)} rows to {OUT_PATH}")
    print(f"Date range: {out['datetime'].min()}  ->  {out['datetime'].max()}")
    print("\nHEAD:")
    print(out.head().to_string())
    print("\nTAIL:")
    print(out.tail().to_string())

if __name__ == "__main__":
    main()
