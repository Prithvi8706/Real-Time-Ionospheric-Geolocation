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
The GP models are trained and evaluated on residuals from the same AH223 ionosonde station (Ahmedabad, 23°N). There is no held-out station for generalisation testing. Performance numbers reflect interpolation within the training distribution, not generalisation to new locations. Document explicitly in the technical report limitations section.

---

### 4. OMNI-web F10.7 auto-lookup
`LocateRequest.f107` was added in D9 so callers can supply the solar flux index explicitly (default 130.0 SFU). The next step is a lightweight OMNI-web lookup by date so callers do not need to supply it manually. Implementation: fetch hourly OMNI2 CSV for the request date, parse F10.7 column, cache per-date to avoid repeated HTTP calls.
No other files need to be touched for this task.
