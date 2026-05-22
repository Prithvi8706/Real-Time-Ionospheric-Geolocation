import os
import pandas as pd

RAW_PATH = os.path.join("data", "raw", "ahmedabad_hmF2_2012_2013.csv")
OMNI_PATH = os.path.join("data", "processed", "omni_indices_2012_2013.csv")
OUT_PATH = os.path.join("data", "processed", "ah223_merged_2012_2013.csv")

def main():
    # --- Load AH223 ---
    ah = pd.read_csv(RAW_PATH)
    n_original = len(ah)

    ah["datetime"] = pd.to_datetime(ah["time"], utc=True)

    # Drop exact duplicate rows
    ah = ah.drop_duplicates()
    n_after_dedup = len(ah)

    # High-confidence filter
    ah = ah[ah["cs"] >= 90].copy()
    n_after_cs = len(ah)

    ah = ah[["datetime", "hmF2", "cs"]].sort_values("datetime").reset_index(drop=True)

    # --- Load OMNI ---
    omni = pd.read_csv(OMNI_PATH)
    omni["datetime"] = pd.to_datetime(omni["datetime"], utc=True)
    omni = omni.sort_values("datetime").reset_index(drop=True)

    # --- Safety asserts: both must be tz-aware UTC ---
    assert ah["datetime"].dt.tz is not None, "AH223 datetime is not tz-aware"
    assert omni["datetime"].dt.tz is not None, "OMNI datetime is not tz-aware"

    # --- Backward as-of merge: each AH223 row gets most recent prior OMNI hour ---
    merged = pd.merge_asof(
        ah,
        omni,
        on="datetime",
        direction="backward",
        tolerance=pd.Timedelta("1h"),
    )

    # Report rows with no OMNI match within tolerance
    nan_mask = merged[["kp", "dst", "f107"]].isna().any(axis=1)
    n_nan = int(nan_mask.sum())

    merged_clean = merged[~nan_mask].copy()
    n_final = len(merged_clean)

    out = merged_clean[["datetime", "hmF2", "cs", "kp", "dst", "f107"]].reset_index(drop=True)
    out.to_csv(OUT_PATH, index=False)

    print(f"Original rows           : {n_original}")
    print(f"After dedup             : {n_after_dedup}")
    print(f"After cs>=90 filter      : {n_after_cs}")
    print(f"Rows w/ no OMNI match    : {n_nan}")
    print(f"Final merged rows        : {n_final}")
    print(f"Saved to {OUT_PATH}")
    print(f"\nDate range: {out['datetime'].min()}  ->  {out['datetime'].max()}")
    print("\nHEAD:")
    print(out.head().to_string())
    print("\nTAIL:")
    print(out.tail().to_string())
    print("\nINDEX SUMMARY:")
    print(out[["kp", "dst", "f107"]].describe().to_string())

if __name__ == "__main__":
    main()
