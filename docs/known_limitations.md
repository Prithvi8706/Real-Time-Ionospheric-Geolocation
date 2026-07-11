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

**Resolved 2026-07-11.** The ray tracer now runs at the request frequency
(`get_rayhf_profile(..., frequency_mhz=...)`, threaded from `ssl_locate`),
the storm residuals were regenerated at request frequencies
(`data/regen_storm_residuals.py`), and the storm GP pair was retrained
(`ml/retrain_storm_gp.py`).

The fix also uncovered and corrected a `find_vh` shape misuse: the wrapper
fed `(n_alts, 1)` arrays into a function that integrates over axis 1, so it
returned a per-layer value instead of the vertical group-refractive-index
integral. Consequences of the corrected physics, documented in
`docs/results.md`: 163 of 229 storm-condition rows penetrate the ionosphere
at their request frequency (correctly no skywave return → IRI fallback),
and the pre-D8 storm figures (610.80 → 111.96 km) are superseded — most of
that "learnable" bias was the physics artifact. A penetration guard now
rejects frequencies the profile cannot reflect.

---

## 4. F10.7 defaults to 130 SFU if not supplied (D9)

`LocateRequest.f107` defaults to **130.0 SFU**, the approximate F10.7
value during the Solar Cycle 24 peak period used in training. This default
is correct for 2012 data but incorrect for other solar epochs.

**Resolved 2026-07-11.** An omitted `f107` is now auto-resolved from the
NASA OMNI2 daily file for the request date (`api/f107.py`; per-date cache,
offline fail-soft to the 130.0 SFU default). The response reports
`f107_used` and `f107_source` ("caller" / "omniweb" / "default"). The
default only applies when the caller omits the value *and* the OMNI2
lookup is unavailable (e.g. air-gapped deployment).

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

## 6. Storm GP trained on only 52 rows (small population)

After the D8 regeneration the PyRayHF storm population contains **66 total
rows** (52 training, 14 test) — the other 163 storm-condition rows
penetrate at their request frequency and fall back to IRI, where no GP
applies. This is a very small sample for a Gaussian Process model. In
practice:

- The test-fold MAE (405.90 km baseline → 379.64 km corrected, 6.5%) is
  based on 14 test rows. Variance on this estimate is very high.
- The longitude GP kernel collapses at this data volume (length scale
  → 2.5e-4, mean σ_lon ≈ 7.9°) — the correction is marginal and should be
  treated as such.
- The GP cannot meaningfully distinguish between different storm
  severities (Kp=5 vs Kp=9) given so few training points across the
  storm-intensity dimension.
- `ood_warning` should be taken seriously for any storm request that
  differs substantially from the training distribution.

**Fix path:** Collect more storm-time ionosonde data (real or modelled)
from the target region and season to expand the PyRayHF training
population. Severity upgraded from Medium to High for storm-time use.

---

## 7. Two-call model inconsistency at latitude boundaries (TODOS item 1)

**Resolved 2026-07-11.** The refined pass now pins the rough pass's model
selection via `get_ionosphere(force_model=...)`, so a midpoint crossing
the ±60° boundary can no longer silently mix model families. Runtime
fallback (e.g. IRTAM → IRI on missing coefficients) still applies within
the pinned branch.

---

## 8. Antimeridian longitude error (TODOS item 2)

**Resolved 2026-07-11.** The refined-pass midpoint longitude now uses a
circular mean (`_circular_mean_deg` in `models/ssl_algorithm.py`), which
equals the arithmetic bisector at mid-latitudes (validated numbers
unchanged) and normalizes the midpoint into [−180, 180] before it reaches
the ionospheric models.

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
| 3 | PyRayHF fixed at 5 MHz (D8) | Storm GP accuracy | Resolved 2026-07-11 | Fixed |
| 4 | F10.7 defaults to 130 SFU (D9) | Non-2012 deployments | Resolved 2026-07-11 (OMNI2 auto-lookup) | Fixed |
| 5 | A-CHAIM never fires at India | A-CHAIM branch untested | No | Low |
| 6 | Storm GP: 52 training rows | Storm estimate confidence | Yes (storm conditions only) | High |
| 7 | Two-call model inconsistency at 60°N | Model selection audit | Resolved 2026-07-11 | Fixed |
| 8 | Antimeridian midpoint arithmetic | Extreme eastern longitudes | Resolved 2026-07-11 | Fixed |
| 9 | No inter-annual validation | Long-term generalization | N/A | Scope |
