# Known Limitations — Real-Time Ionospheric Geolocation

**Problem ID:** DRDO DIA-CoE/EW/02  
**Status:** Post-engineering-review. Items below are documented limitations,
not bugs — the system operates correctly within its stated scope.

---

## 1. Scope: single station, three months, simulated geometry

All training data, validation data, and published performance figures come
from a single ionosonde station: **AH223 Ahmedabad (23.0°N, 72.6°E)**,
covering **June, July, and December 2012** only (Solar Cycle 24 peak).
The emitter geometry is **single-hop simulated**, not real emitter tracks.

Implications:
- Performance figures are interpolation within this distribution, not
  generalization estimates.
- No claim is made about accuracy at other stations, other latitudes,
  other months, or other solar cycle phases.
- Deploying the system at a mid-latitude northern European or polar
  station without retraining the GP would produce uncorrected (or
  misdirected) residuals.

**Mitigation:** Retrain the GP on residuals from the target station and
season. The training script (`models/ssl_gp_model.py`) accepts any
residuals CSV in the expected format.

---

## 2. GP not validated on held-out data (Approach B pending)

The GP is trained and tested on the same single station (AH223). There is
no held-out ionosonde station used exclusively for evaluation. This means
the test-set MAE figures (77.15 km for IRTAM, 111.96 km for PyRayHF) are
within-distribution scores, not cross-station generalization scores.

**Approach B** — training on a set of stations and testing on a held-out
station — is the correct next validation step and is not yet implemented.
Until Approach B is complete, do not interpret the published figures as
estimates of performance at an arbitrary new location.

---

## 3. PyRayHF calibrated at 5 MHz only (D8)

The PyRayHF ray tracer runs at a fixed internal frequency of **5.0 MHz**,
which is representative of AH223 solar maximum conditions. The storm GP
models (`gp_lat_sami3.pkl`, `gp_lon_sami3.pkl`) were also trained at this
frequency.

When a caller passes `frequency_mhz = 10.0` (for example), the SSL
physics estimate is computed at 10 MHz but the GP correction was trained
with the ray tracer operating at 5 MHz. The feature vector fed to the GP
includes `frequency_mhz` from the request (10 MHz) while the underlying
physics (`virtual_height_km`) was derived at 5 MHz. This inconsistency
affects the GP prediction for the PyRayHF population.

**Fix path:** Expose `_F_MHZ` in `rayhf_wrapper.py` as a parameter and
re-run the PyRayHF ray tracer at the request frequency, then retrain the
storm GP at matching frequencies.

---

## 4. F10.7 defaults to 130 SFU if not supplied (D9)

`LocateRequest.f107` defaults to **130.0 SFU**, the approximate F10.7
value during the Solar Cycle 24 peak period used in training. This default
is correct for 2012 data but incorrect for other solar epochs.

A caller who does not supply `f107` for a 2025 observation (Solar Cycle
25 rising phase, F10.7 ≈ 160–200 SFU) will receive an estimate that uses
an incorrect solar flux index, degrading ionospheric model accuracy.

**Fix path (deferred):** Implement a lightweight OMNI-web lookup that
fetches the daily F10.7 value from NASA's OMNI2 dataset by date and
injects it automatically. The `LocateRequest` field and its validator are
already in place; only the fetch logic is missing.

---

## 5. A-CHAIM never fires at India geometry

A-CHAIM is invoked only when |latitude| ≥ 60°. The AH223 Ahmedabad
station is at 23°N; in any plausible India-region demo the A-CHAIM branch
will never be selected. The model is present for deployment completeness
at polar or sub-polar sites (e.g., Antarctic stations, Canadian Arctic).

If the system is demonstrated exclusively at mid-latitude India geometry,
the A-CHAIM path receives no test coverage in that environment. The
regression test suite does not include an A-CHAIM path test.

---

## 6. Storm GP trained on only 183 rows (small population)

The PyRayHF storm population contains **229 total rows** (183 training,
46 test). This is a small sample for a Gaussian Process model. The GP
posterior uncertainty will be well-calibrated near training points but
will inflate rapidly away from them. In practice:

- The test-set MAE of 111.96 km is based on 46 test rows. Variance on
  this estimate is high.
- The GP cannot meaningfully distinguish between different storm
  severities (Kp=5 vs Kp=9) given so few training points across the
  storm-intensity dimension.
- `ood_warning` should be taken seriously for any storm request that
  differs substantially from the training distribution.

**Fix path:** Collect more storm-time ionosonde data (real or modelled)
from the target region and season to expand the PyRayHF training population.

---

## 7. Two-call model inconsistency at latitude boundaries (TODOS item 1)

`ssl_locate()` calls `get_ionosphere()` twice: once at the receiver
location (rough pass) and once at the midpoint (refined pass). If the
midpoint happens to cross the A-CHAIM latitude boundary (|lat| = 60°),
the two calls may select different models — IRI for the receiver, A-CHAIM
for the midpoint — producing an inconsistent profile pair.

This never fires at India geometry (23°N) but would manifest at ~55°N
deployment. The fix is to propagate the model selected in the rough pass
into the refined pass, or assert both calls return the same model.

---

## 8. Antimeridian longitude error (TODOS item 2)

The midpoint longitude is computed as simple arithmetic mean:

```python
mid_lon = (receiver_lon + rough_tx_lon) / 2
```

This is incorrect when the receiver and rough transmitter straddle the
antimeridian (longitude ±180°). For example, averaging 170°E and −170°E
gives 0° instead of the correct 180°. The fix is to use circular mean
arithmetic for longitude.

This does not affect any India-region demo (all longitudes well away
from 180°).

---

## 9. No held-out temporal validation

The 2012 dataset spans three months. No evaluation has been performed on
data from other years. Solar cycle variation, inter-annual ionospheric
variability, and long-term drift in ionosonde calibration are not
captured by the training data and not reflected in the published figures.

---

## Summary table

| # | Limitation | Scope affected | Fires at AH223 23°N demo? | Severity |
|---|---|---|---|---|
| 1 | Single station/season/geometry scope | All performance claims | N/A — it is the deployment site | Scope |
| 2 | GP not validated on held-out station | Generalization claims | N/A | Scope |
| 3 | PyRayHF fixed at 5 MHz (D8) | Storm GP accuracy | Yes, for non-5 MHz requests | Medium |
| 4 | F10.7 defaults to 130 SFU (D9) | Non-2012 deployments | No for 2012 data | Low |
| 5 | A-CHAIM never fires at India | A-CHAIM branch untested | No | Low |
| 6 | Storm GP: 183 training rows | Storm estimate confidence | Yes (storm conditions only) | Medium |
| 7 | Two-call model inconsistency at 60°N | Model selection audit | No | Low |
| 8 | Antimeridian midpoint arithmetic | Extreme eastern longitudes | No | Low |
| 9 | No inter-annual validation | Long-term generalization | N/A | Scope |
