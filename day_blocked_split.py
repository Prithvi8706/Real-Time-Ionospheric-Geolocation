"""
Day-blocked train/test split study.

The published figures (docs/results.md) use a row-level random 80/20 split.
Ionospheric residuals are temporally autocorrelated, so adjacent-hour rows
straddling the train/test boundary can flatter the corrected MAE. This study
re-trains the GP pairs with the split blocked by calendar day — no day
contributes rows to both folds — and reports the same statistics.

Comparison-only: production models in models/saved/ are NOT overwritten.
Same kernel, training code, and seed conventions as models/ssl_gp_model.py.

Run from repo root (long: full IRTAM GP fit, possibly 30+ min):
    python day_blocked_split.py
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

from models.ssl_gp_model import load_and_prepare, _train_pair, haversine_error_km

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "data", "processed", "ssl_real_residuals_2012.csv")
TEST_FRAC = 0.2
SEED = 42


def day_blocked_masks(days, test_frac=TEST_FRAC, seed=SEED):
    """
    Split rows by calendar day: shuffle unique days (seeded), take ~test_frac
    of days as the test fold. No day contributes rows to both folds.
    Returns (train_mask, test_mask) boolean arrays over rows.
    """
    unique_days = np.array(sorted(set(days)))
    rng = np.random.default_rng(seed)
    rng.shuffle(unique_days)
    n_test_days = max(1, int(round(len(unique_days) * test_frac)))
    test_days = set(unique_days[:n_test_days])
    is_test = np.array([d in test_days for d in days])
    return ~is_test, is_test


def _stats(errors, label):
    e = np.asarray(errors)
    print(f"  {label:22s} MAE={e.mean():8.2f}  median={np.median(e):8.2f}  "
          f"P90={np.quantile(e, 0.9):8.2f}  max={e.max():8.2f}  (n={len(e)})",
          flush=True)
    return e


def evaluate_population(tag, X_pop, ylat_pop, ylon_pop, df_pop):
    days = pd.to_datetime(df_pop["dt"]).dt.date.values
    train_mask, test_mask = day_blocked_masks(days)
    n_days = len(set(days))
    n_test_days = len(set(days[test_mask]))

    print(f"\n=== {tag} — day-blocked split ===", flush=True)
    print(f"  Days: {n_days} total, {n_test_days} test | "
          f"Rows: {train_mask.sum()} train, {test_mask.sum()} test "
          f"({test_mask.sum() / len(days) * 100:.1f}% test rows)", flush=True)

    gp_lat, gp_lon = _train_pair(
        X_pop[train_mask], ylat_pop[train_mask], ylon_pop[train_mask], tag)

    pred_lat = gp_lat.predict(X_pop[test_mask])
    pred_lon = gp_lon.predict(X_pop[test_mask])

    b_lat = df_pop["baseline_lat"].values[test_mask]
    b_lon = df_pop["baseline_lon"].values[test_mask]
    t_lat = df_pop["tx_lat"].values[test_mask]
    t_lon = df_pop["tx_lon"].values[test_mask]

    baseline_err = haversine_error_km(b_lat, b_lon, t_lat, t_lon)
    corrected_err = haversine_error_km(b_lat + pred_lat, b_lon + pred_lon,
                                       t_lat, t_lon)

    b = _stats(baseline_err, "Baseline (day-blocked)")
    c = _stats(corrected_err, "GP corrected (day-bl.)")
    print(f"  {'Improvement':22s} {b.mean() - c.mean():8.2f} km "
          f"({(1 - c.mean() / b.mean()) * 100:.1f}%)", flush=True)


def main():
    X, y_lat, y_lon, df, _ = load_and_prepare(CSV)

    mask_irtam = (df["model_used"] == "IRTAM").values
    df_irtam = df[mask_irtam].reset_index(drop=True)
    evaluate_population("IRTAM", X[mask_irtam],
                        y_lat[mask_irtam], y_lon[mask_irtam], df_irtam)

    mask_storm = df["model_used"].isin(["SAMI3", "PyRayHF"]).values
    df_storm = df[mask_storm].reset_index(drop=True)
    n_storm_days = pd.to_datetime(df_storm["dt"]).dt.date.nunique()
    if n_storm_days >= 5:
        print(f"\nNOTE: storm population spans only {n_storm_days} days — "
              "the day-blocked storm result below is close to meaningless "
              "and is reported for completeness only.", flush=True)
        evaluate_population("PyRayHF/storm", X[mask_storm],
                            y_lat[mask_storm], y_lon[mask_storm], df_storm)
    else:
        print(f"\nSkipping storm population: only {n_storm_days} distinct days "
              "— too few to day-block.", flush=True)

    print("\nDAY_BLOCKED_STUDY_DONE", flush=True)


if __name__ == "__main__":
    main()
