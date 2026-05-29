# Validated Results — Real-Time Ionospheric Geolocation

**Problem ID:** DRDO DIA-CoE/EW/02  
**Station:** AH223 Ahmedabad (23.0°N, 72.6°E)  
**Period:** June, July, December 2012 (Solar Cycle 24 peak)  
**Geometry:** Single-hop, simulated emitter  
**Metric:** Mean Absolute Error (MAE) in km, Haversine distance

---

## Scope statement

All numbers in this document describe **interpolation performance within
the training distribution**. The GP models were trained and evaluated on
residuals from the same station and the same three months. There is no
held-out station or held-out time period. These figures measure how well
the system reduces bias on data it was exposed to during training; they
do not measure generalization to new locations, other ionosonde stations,
or months outside {June, July, December}. A held-out generalization test
(Approach B) is pending.

---

## Dataset composition

| Population | Rows | Share | Ionospheric model |
|---|---|---|---|
| IRTAM (nominal conditions) | 9,228 | 97.6% | PyIRTAM local cache |
| PyRayHF (storm: Kp ≥ 5 or Dst ≤ −100 nT) | 229 | 2.4% | PyRayHF ray tracer |
| **Total** | **9,457** | **100%** | — |

GP training uses an 80/20 train/test split (random seed 42) applied
**within each population separately**.

| Population | Training rows | Test rows |
|---|---|---|
| IRTAM | 7,382 | 1,846 |
| PyRayHF | 183 | 46 |

---

## Performance results

| Population | Test rows | Baseline MAE (physics only) | GP-Corrected MAE | Improvement (km) | Improvement (%) |
|---|---|---|---|---|---|
| IRTAM | 1,846 | 103.29 km | 77.15 km | 26.14 km | 25.3% |
| PyRayHF (storm) | 46 | 610.80 km | 111.96 km | 498.84 km | 81.7% |

**Baseline** is the SSL physics estimate with no GP correction applied
(`primary_estimate` in the API response).

**GP-Corrected** is the SSL estimate plus the GP residual prediction
(`gp_correction.corrected_lat / corrected_lon` in the API response).

Both MAE values are computed on the held-out 20% test split. They are
not computed on the training data.

---

## Numbers never to cite

The following figures appeared in earlier development runs and are not
valid:

| Figure | Why invalid |
|---|---|
| 96 km / 66.55 km (30.7% improvement) | Fabricated; produced from a synthetic GP training run, not real residuals |
| 104.55 km / 74.67 km (28.6% improvement) | Mixed-population baseline — IRTAM and PyRayHF rows combined into a single GP, causing kernel collapse. Not per-population figures |

Use only the per-population figures from the table above.

---

## Interpretation

**IRTAM population (97.6% of data):** Under nominal mid-latitude
conditions the SSL physics estimate has a baseline error of ~103 km.
The GP correction reduces this to ~77 km, a 25% improvement. The
improvement reflects systematic, learnable bias in the SSL formula under
the Solar Cycle 24 ionospheric conditions seen at Ahmedabad in 2012.

**PyRayHF storm population (2.4% of data):** Under geomagnetic storm
conditions the SSL physics estimate degrades substantially (baseline ~611 km).
This large error is a known characteristic of SSL geolocation during
storms: the F2 layer is severely disturbed, and the virtual height
produced by the ray tracer captures only part of the distortion. The
GP correction reduces the error to ~112 km (81.7% improvement). However,
this result is based on only 229 total rows (183 training, 46 test).
The small population means the GP has limited ability to generalise
across the full space of storm conditions. Treat this figure with caution.

---

## GP uncertainty output

Each GP prediction includes a posterior standard deviation. The API
returns these as `uncertainty_lat_deg`, `uncertainty_lon_deg`, and the
combined `correction_std_km`. These are the GP's own confidence estimates
about its predicted residual, not end-to-end location error bounds.
When `ood_warning = true` the GP posterior uncertainty should be treated
as a lower bound — the actual error may be larger outside the training
distribution.

---

## What this system does not claim

- Performance at stations other than AH223 Ahmedabad.
- Performance in months other than June, July, or December 2012.
- Performance during multi-hop propagation.
- Generalization to other solar cycle phases.
- Real-time ionosonde assimilation beyond the IRTAM coefficient cache.
- End-to-end closed-loop operation with live ionosonde feed.

Approach B (held-out station generalization test) is the recommended next
validation step before claiming generalizable accuracy.
