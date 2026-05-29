import numpy as np
import pandas as pd
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.model_selection import train_test_split
import joblib
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(_ROOT, "models", "saved")
os.makedirs(MODEL_DIR, exist_ok=True)


def haversine_error_km(lat1, lon1, lat2, lon2):
    """Compute distance in km between predicted and true location."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))


def load_and_prepare(csv_path: str):
    """Load real residuals dataset and extract features + targets."""
    df = pd.read_csv(csv_path)
    df["hour"]  = pd.to_datetime(df["dt"]).dt.hour
    df["month"] = pd.to_datetime(df["dt"]).dt.month

    features = [
        "azimuth", "elevation", "frequency_mhz",
        "virtual_height_km", "kp", "dst",
        "hour", "month",
        "baseline_lat", "baseline_lon"
    ]

    X = df[features].values
    y_lat = df["residual_lat"].values
    y_lon = df["residual_lon"].values

    return X, y_lat, y_lon, df, features


def build_kernel():
    """RBF captures smooth spatial variation, WhiteKernel captures noise."""
    return RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)


def _train_pair(X_train, ylat_train, ylon_train, tag: str):
    """Train a lat+lon GP pair on the given training split. Returns (gp_lat, gp_lon)."""
    print(f"Training GP for latitude residual  [{tag}]...")
    gp_lat = GaussianProcessRegressor(
        kernel=build_kernel(),
        n_restarts_optimizer=3,
        normalize_y=True
    )
    gp_lat.fit(X_train, ylat_train)
    print(f"  Kernel: {gp_lat.kernel_}")

    print(f"Training GP for longitude residual [{tag}]...")
    gp_lon = GaussianProcessRegressor(
        kernel=build_kernel(),
        n_restarts_optimizer=3,
        normalize_y=True
    )
    gp_lon.fit(X_train, ylon_train)
    print(f"  Kernel: {gp_lon.kernel_}")

    return gp_lat, gp_lon


def _evaluate(gp_lat, gp_lon, X_test, idx_test, df, tag: str):
    """Evaluate a GP pair on a test split and print results."""
    pred_lat, std_lat = gp_lat.predict(X_test, return_std=True)
    pred_lon, std_lon = gp_lon.predict(X_test, return_std=True)

    baseline_lat = df["baseline_lat"].values[idx_test]
    baseline_lon = df["baseline_lon"].values[idx_test]
    true_lat     = df["tx_lat"].values[idx_test]
    true_lon     = df["tx_lon"].values[idx_test]

    final_lat = baseline_lat + pred_lat
    final_lon = baseline_lon + pred_lon

    errors_km = [
        haversine_error_km(final_lat[i], final_lon[i], true_lat[i], true_lon[i])
        for i in range(len(final_lat))
    ]
    baseline_errors_km = [
        haversine_error_km(baseline_lat[i], baseline_lon[i], true_lat[i], true_lon[i])
        for i in range(len(baseline_lat))
    ]

    print(f"\n=== RESULTS [{tag}] ===")
    print(f"Test rows                     : {len(X_test)}")
    print(f"Baseline error (physics only) : {np.mean(baseline_errors_km):.2f} km")
    print(f"GP corrected error            : {np.mean(errors_km):.2f} km")
    print(f"Improvement                   : {np.mean(baseline_errors_km) - np.mean(errors_km):.2f} km")
    print(f"Mean uncertainty (lat std)    : {np.mean(std_lat):.4f}°")
    print(f"Mean uncertainty (lon std)    : {np.mean(std_lon):.4f}°")
    print(f"Max error                     : {np.max(errors_km):.2f} km")
    print(f"Min error                     : {np.min(errors_km):.2f} km")

    return np.mean(errors_km), np.mean(baseline_errors_km)


def train_gp(csv_path: str = None):
    """
    Train per-population GPs — one pair for IRTAM rows, one pair for PyRayHF rows.

    IRTAM and PyRayHF rows have structurally different error patterns.
    Mixing them into a single GP causes the latitude kernel to collapse (length_scale
    near zero, WhiteKernel at lower bound). Training separately recovers the structure.

    Saves four models:
        gp_lat_irtam.pkl, gp_lon_irtam.pkl   — nominal ionosphere (97.6% of rows)
        gp_lat_sami3.pkl, gp_lon_sami3.pkl   — storm rows via PyRayHF (2.4% of rows)

    D5 fix: mask_sami3 accepts both 'SAMI3' and 'PyRayHF' labels so residual
    CSVs generated after the model rename do not silently drop all storm rows.
    """
    if csv_path is None:
        csv_path = os.path.join(_ROOT, "data", "processed", "ssl_real_residuals_2012.csv")

    print("Loading dataset...")
    X, y_lat, y_lon, df, features = load_and_prepare(csv_path)

    # --- Split by model population ---
    mask_irtam = (df["model_used"] == "IRTAM").values
    # D5 fix: accept both legacy 'SAMI3' label and current 'PyRayHF' label
    mask_sami3 = df["model_used"].isin(["SAMI3", "PyRayHF"]).values

    print(f"\nPopulation split:")
    print(f"  IRTAM        : {mask_irtam.sum()} rows")
    print(f"  PyRayHF/SAMI3: {mask_sami3.sum()} rows")

    # ── IRTAM population ─────────────────────────────────────────────────────
    X_irtam    = X[mask_irtam]
    ylat_irtam = y_lat[mask_irtam]
    ylon_irtam = y_lon[mask_irtam]
    idx_irtam  = np.where(mask_irtam)[0]

    X_tr, X_te, ylat_tr, ylat_te, ylon_tr, ylon_te, idx_tr, idx_te = train_test_split(
        X_irtam, ylat_irtam, ylon_irtam, idx_irtam,
        test_size=0.2, random_state=42
    )
    print(f"\nIRTAM — Train: {len(X_tr)} | Test: {len(X_te)}")
    gp_lat_irtam, gp_lon_irtam = _train_pair(X_tr, ylat_tr, ylon_tr, "IRTAM")
    _evaluate(gp_lat_irtam, gp_lon_irtam, X_te, idx_te, df, "IRTAM")

    # ── PyRayHF / SAMI3 population ───────────────────────────────────────────
    X_sami3    = X[mask_sami3]
    ylat_sami3 = y_lat[mask_sami3]
    ylon_sami3 = y_lon[mask_sami3]
    idx_sami3  = np.where(mask_sami3)[0]

    # 229 rows total — use 80/20 split but note the test set will be small (~45 rows)
    X_tr2, X_te2, ylat_tr2, ylat_te2, ylon_tr2, ylon_te2, idx_tr2, idx_te2 = train_test_split(
        X_sami3, ylat_sami3, ylon_sami3, idx_sami3,
        test_size=0.2, random_state=42
    )
    print(f"\nPyRayHF/SAMI3 — Train: {len(X_tr2)} | Test: {len(X_te2)}")
    gp_lat_sami3, gp_lon_sami3 = _train_pair(X_tr2, ylat_tr2, ylon_tr2, "PyRayHF/SAMI3")
    _evaluate(gp_lat_sami3, gp_lon_sami3, X_te2, idx_te2, df, "PyRayHF/SAMI3")

    # ── Save all four models ──────────────────────────────────────────────────
    joblib.dump(gp_lat_irtam,  f"{MODEL_DIR}/gp_lat_irtam.pkl")
    joblib.dump(gp_lon_irtam,  f"{MODEL_DIR}/gp_lon_irtam.pkl")
    joblib.dump(gp_lat_sami3,  f"{MODEL_DIR}/gp_lat_sami3.pkl")
    joblib.dump(gp_lon_sami3,  f"{MODEL_DIR}/gp_lon_sami3.pkl")
    print(f"\nModels saved to {MODEL_DIR}/")
    print("  gp_lat_irtam.pkl, gp_lon_irtam.pkl")
    print("  gp_lat_sami3.pkl, gp_lon_sami3.pkl")

    return gp_lat_irtam, gp_lon_irtam, gp_lat_sami3, gp_lon_sami3


if __name__ == "__main__":
    train_gp()