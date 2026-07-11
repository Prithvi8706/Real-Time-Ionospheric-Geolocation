"""
Retrain ONLY the storm (PyRayHF) GP pair after the D8 fix.

The IRTAM pair is untouched: D8 changed nothing for IRTAM rows, and
retraining 7,382 rows would burn hours for a byte-identical result.
Reuses the exact split/kernel/training code from models/ssl_gp_model.py.

Run from repo root:
    python ml/retrain_storm_gp.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import joblib
from sklearn.model_selection import train_test_split

from models.ssl_gp_model import (
    load_and_prepare, _train_pair, _evaluate, MODEL_DIR, _ROOT,
)

CSV = os.path.join(_ROOT, "data", "processed", "ssl_real_residuals_2012.csv")


def main():
    X, y_lat, y_lon, df, _ = load_and_prepare(CSV)
    mask = df["model_used"].isin(["SAMI3", "PyRayHF"]).values
    print(f"Storm population: {mask.sum()} rows")

    Xp, ylat_p, ylon_p = X[mask], y_lat[mask], y_lon[mask]
    idx_p = np.where(mask)[0]

    X_tr, X_te, ylat_tr, ylat_te, ylon_tr, ylon_te, idx_tr, idx_te = \
        train_test_split(Xp, ylat_p, ylon_p, idx_p,
                         test_size=0.2, random_state=42)
    print(f"Train: {len(X_tr)} | Test: {len(X_te)}")

    gp_lat, gp_lon = _train_pair(X_tr, ylat_tr, ylon_tr, "PyRayHF/D8")
    _evaluate(gp_lat, gp_lon, X_te, idx_te, df, "PyRayHF/D8")

    joblib.dump(gp_lat, os.path.join(MODEL_DIR, "gp_lat_sami3.pkl"))
    joblib.dump(gp_lon, os.path.join(MODEL_DIR, "gp_lon_sami3.pkl"))
    print(f"Saved storm GP pair to {MODEL_DIR}")


if __name__ == "__main__":
    main()
