"""
Table 2/3 statistics for the DRDO DIA-CoE/EW/02 technical report.

Place this file in the REPO ROOT (same level as models/ and data/), then run:

    & "C:\\Users\\prith\\anaconda3\\python.exe" report_table3.py

It does NOT retrain anything. It recreates the exact deterministic 80/20
split from models/ssl_gp_model.py (random_state=42), loads the saved GP
models from models/saved/, and prints baseline + corrected error statistics
on the held-out test folds. Paste the FULL output back into the conversation.
"""
import os
import numpy as np
import pandas as pd
import joblib
import sklearn
from sklearn.model_selection import train_test_split

_ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(_ROOT, "data", "processed", "ssl_real_residuals_2012.csv")
MODEL_DIR = os.path.join(_ROOT, "models", "saved")

print(f"scikit-learn version: {sklearn.__version__}")
print(f"Residual CSV        : {CSV}")
print(f"Model dir           : {MODEL_DIR}")
print(f"Models present      : {sorted(os.listdir(MODEL_DIR))}")
print()


def haversine_error_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


# --- identical preparation to models/ssl_gp_model.py ---
df = pd.read_csv(CSV)
df["hour"] = pd.to_datetime(df["dt"]).dt.hour
df["month"] = pd.to_datetime(df["dt"]).dt.month

features = [
    "azimuth", "elevation", "frequency_mhz",
    "virtual_height_km", "kp", "dst",
    "hour", "month",
    "baseline_lat", "baseline_lon",
]
X = df[features].values
y_lat = df["residual_lat"].values
y_lon = df["residual_lon"].values

mask_irtam = (df["model_used"] == "IRTAM").values
mask_sami3 = df["model_used"].isin(["SAMI3", "PyRayHF"]).values


def stats(errors, label):
    e = np.asarray(errors)
    print(f"  {label:22s} MAE={e.mean():8.2f}  median={np.median(e):8.2f}  "
          f"P90={np.quantile(e, 0.9):8.2f}  max={e.max():8.2f}  (n={len(e)})")
    return e


def evaluate_population(mask, lat_pkl, lon_pkl, tag):
    Xp = X[mask]
    ylat_p = y_lat[mask]
    ylon_p = y_lon[mask]
    idx_p = np.where(mask)[0]

    # identical split call to models/ssl_gp_model.py -> deterministic
    (X_tr, X_te,
     ylat_tr, ylat_te,
     ylon_tr, ylon_te,
     idx_tr, idx_te) = train_test_split(
        Xp, ylat_p, ylon_p, idx_p, test_size=0.2, random_state=42
    )

    gp_lat = joblib.load(os.path.join(MODEL_DIR, lat_pkl))
    gp_lon = joblib.load(os.path.join(MODEL_DIR, lon_pkl))

    pred_lat = gp_lat.predict(X_te)
    pred_lon = gp_lon.predict(X_te)

    b_lat = df["baseline_lat"].values[idx_te]
    b_lon = df["baseline_lon"].values[idx_te]
    t_lat = df["tx_lat"].values[idx_te]
    t_lon = df["tx_lon"].values[idx_te]

    f_lat = b_lat + pred_lat
    f_lon = b_lon + pred_lon

    baseline_err = haversine_error_km(b_lat, b_lon, t_lat, t_lon)
    corrected_err = haversine_error_km(f_lat, f_lon, t_lat, t_lon)

    print(f"=== {tag} ===")
    print(f"  Population: {mask.sum()} rows | Train: {len(X_tr)} | Held-out test: {len(X_te)}")
    b = stats(baseline_err, "Baseline (test fold)")
    c = stats(corrected_err, "GP corrected (test)")
    print(f"  {'Improvement':22s} {b.mean() - c.mean():8.2f} km "
          f"({(1 - c.mean() / b.mean()) * 100:.1f}%)")
    print()


evaluate_population(mask_irtam, "gp_lat_irtam.pkl", "gp_lon_irtam.pkl",
                    "IRTAM (nominal mid-latitude)")
evaluate_population(mask_sami3, "gp_lat_sami3.pkl", "gp_lon_sami3.pkl",
                    "PyRayHF/SAMI3 (storm)")

print("Done. Paste everything above back into the conversation.")
