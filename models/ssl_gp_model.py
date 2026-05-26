import numpy as np
import pandas as pd
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
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

    # Real residuals already computed by generate_real_residuals.py
    # baseline_* = SSL estimate using model height
    # tx_*       = known true emitter location
    # residual_* = true - baseline (real physics error, not injected noise)

    features = [
        "azimuth", "elevation", "frequency_mhz",
        "virtual_height_km", "kp", "dst",
        "hour", "month",
        "baseline_lat", "baseline_lon"
    ]

    X = df[features].values
    y_lat = df["residual_lat"].values
    y_lon = df["residual_lon"].values
    df_out = df

    return X, y_lat, y_lon, df_out, features

def build_kernel():
    """RBF captures smooth spatial variation, WhiteKernel captures noise."""
    return RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)

def train_gp(csv_path: str = None):
    """Train two GPs — one for lat residual, one for lon residual."""

    if csv_path is None:
        csv_path = os.path.join(_ROOT, "data", "processed", "ssl_real_residuals_2012.csv")
    print("Loading dataset...")
    X, y_lat, y_lon, df, features = load_and_prepare(csv_path)

    X_train, X_test, \
    ylat_train, ylat_test, \
    ylon_train, ylon_test, \
    idx_train, idx_test = train_test_split(
        X, y_lat, y_lon, np.arange(len(X)),
        test_size=0.2, random_state=42
    )

    print(f"Train: {len(X_train)} rows | Test: {len(X_test)} rows")

    # Train GP for latitude residual
    print("Training GP for latitude residual...")
    gp_lat = GaussianProcessRegressor(
        kernel=build_kernel(),
        n_restarts_optimizer=3,
        normalize_y=True
    )
    gp_lat.fit(X_train, ylat_train)
    print(f"  Kernel: {gp_lat.kernel_}")

    # Train GP for longitude residual
    print("Training GP for longitude residual...")
    gp_lon = GaussianProcessRegressor(
        kernel=build_kernel(),
        n_restarts_optimizer=3,
        normalize_y=True
    )
    gp_lon.fit(X_train, ylon_train)
    print(f"  Kernel: {gp_lon.kernel_}")

    # Predict on test set
    print("Evaluating...")
    pred_lat_residual, std_lat = gp_lat.predict(X_test, return_std=True)
    pred_lon_residual, std_lon = gp_lon.predict(X_test, return_std=True)

    # Final prediction = baseline + GP correction
    baseline_lat_test = df["baseline_lat"].values[idx_test]
    baseline_lon_test = df["baseline_lon"].values[idx_test]
    true_lat_test     = df["tx_lat"].values[idx_test]
    true_lon_test     = df["tx_lon"].values[idx_test]

    final_lat = baseline_lat_test + pred_lat_residual
    final_lon = baseline_lon_test + pred_lon_residual

    # Compute errors
    errors_km = [
        haversine_error_km(final_lat[i], final_lon[i],
                           true_lat_test[i], true_lon_test[i])
        for i in range(len(final_lat))
    ]
    baseline_errors_km = [
        haversine_error_km(baseline_lat_test[i], baseline_lon_test[i],
                           true_lat_test[i], true_lon_test[i])
        for i in range(len(baseline_lat_test))
    ]

    print("\n=== RESULTS ===")
    print(f"Baseline error (physics only) : {np.mean(baseline_errors_km):.2f} km")
    print(f"GP corrected error            : {np.mean(errors_km):.2f} km")
    print(f"Improvement                   : {np.mean(baseline_errors_km) - np.mean(errors_km):.2f} km")
    print(f"Mean uncertainty (lat std)    : {np.mean(std_lat):.4f}°")
    print(f"Mean uncertainty (lon std)    : {np.mean(std_lon):.4f}°")
    print(f"Max error                     : {np.max(errors_km):.2f} km")
    print(f"Min error                     : {np.min(errors_km):.2f} km")

    # Save models
    joblib.dump(gp_lat, f"{MODEL_DIR}/gp_lat.pkl")
    joblib.dump(gp_lon, f"{MODEL_DIR}/gp_lon.pkl")
    print(f"\nModels saved to {MODEL_DIR}/")

    return gp_lat, gp_lon, np.mean(errors_km)

if __name__ == "__main__":
    train_gp()