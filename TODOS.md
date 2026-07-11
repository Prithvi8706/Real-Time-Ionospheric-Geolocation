# TODOS — Real-Time Ionospheric Geolocation
## Known Limitations and Deferred Work

---

### 1. Two-call model inconsistency
**Resolved 2026-07-11** — the refined pass now pins the rough pass's model
selection via `get_ionosphere(force_model=...)`, so a midpoint crossing the
±60° boundary can no longer silently mix model families. Runtime fallback
(e.g. IRTAM → IRI on missing coefficients) still applies within the pinned
branch.

---

### 2. Antimeridian longitude midpoint arithmetic
**Resolved 2026-07-11** — the refined-pass midpoint longitude now uses a
circular mean (`_circular_mean_deg`), which is exactly the arithmetic
bisector at mid-latitudes (validated numbers unchanged) and additionally
normalizes the midpoint into [-180, 180] before it reaches the models.

---

### 3. Training data leakage
**Resolved 2026-07-11** — documented explicitly in the technical report
(Section VI "interpolation, not generalization" and the validity envelope) and
in PROJECT_WALKTHROUGH.md. The underlying limitation (no held-out station)
remains future validation work, tracked in the report's Path to Operational Use.

---

### 4. OMNI-web F10.7 auto-lookup
**Resolved 2026-07-11** — `api/f107.py` auto-resolves omitted `f107` from the
OMNI2 daily file (per-date cache, offline fail-soft to 130.0 SFU); `/locate`
reports `f107_used` and `f107_source`. Wiring f107 into the ionospheric models
remains deferred (couples to D8 PyRayHF frequency parameterisation).
