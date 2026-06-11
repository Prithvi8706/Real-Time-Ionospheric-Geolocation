# Product

## Register

product

## Users

Defence-research evaluators (DRDO DIA-CoE reviewers) and HF propagation researchers assessing a single-station HF emitter geolocation pipeline. They arrive expert in the domain (Kp, Dst, foF2, skywave geometry) and want to probe the system: set intercept parameters, run a solve, inspect the physics and the GP correction, and judge whether the numbers are credible.

## Product Purpose

A console for the SSL (single-station location) pipeline: converts a measured HF arrival bearing + elevation into a transmitter lat/lon using a condition-aware hybrid ionospheric model (PyRayHF / A-CHAIM / PyIRTAM / IRI-2016) plus a GP residual-correction layer. Success: an evaluator can run any scenario, see exactly which model was routed and why, and read honest uncertainty (1σ radius, OOD warnings, MUF warnings) without leaving the screen.

## Brand Personality

Precise, honest, operational. A mission console, not a marketing page: dense, dark, monospace-numbered, every claim qualified (validated MAE in the footer, EXPERIMENTAL tag on the GP section).

## Anti-references

- SaaS dashboard gloss: hero metrics, gradient cards, decorative glassmorphism.
- Consumer-map products (Google Maps look): this is instrument cartography, not navigation.
- Overclaiming UI: nothing may imply validated accuracy beyond the AH223/2012 training distribution.

## Design Principles

1. **Honest instrumentation** — uncertainty, fallbacks, and out-of-distribution states are first-class UI, never hidden.
2. **The route is the story** — model selection logic is visible before and after every solve.
3. **Dense but legible** — expert density, with a strict floor on type size and contrast.
4. **Physics you can see** — hop geometry rendered, not just numbered.
5. **Degrade loudly** — API down, MUF exceeded, GP unavailable each get explicit states.

## Accessibility & Inclusion

WCAG AA target for text contrast; full keyboard operability of the form; `prefers-reduced-motion` honored for all animation; status changes announced via `role="alert"` / `aria-live`.
