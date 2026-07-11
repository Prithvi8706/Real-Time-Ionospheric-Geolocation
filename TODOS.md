# TODOS — Real-Time Ionospheric Geolocation
## Known Limitations and Deferred Work

---

### 1. Two-call model inconsistency
`ssl_locate()` calls `get_ionosphere()` twice — once at the receiver location (rough pass) and once at the midpoint (refined pass). If the midpoint crosses the A-CHAIM latitude boundary (`|lat| >= 60`), the rough call uses IRI but the refined call uses A-CHAIM, producing an inconsistent profile pair. Never triggers at India geometry (23°N) but would fire at 55°N deployment. Fix: pass the model selected in the rough pass through to the refined pass, or assert both calls return the same model.

---

### 2. Antimeridian longitude midpoint arithmetic
The midpoint calculation in `ssl_locate()` uses simple averaging: `mid_lon = (receiver_lon + rough_tx_lon) / 2`. This does not handle antimeridian crossing — emitters near 180° longitude will produce an incorrect midpoint (e.g. averaging 170°E and -170°E gives 0° instead of 180°). Fix: use circular mean for longitude arithmetic.

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
