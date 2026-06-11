# Design

Captured from `api/static/index.html` (single-file UI, no build step, ES5 JS, Leaflet only).

## Theme

Dark ops-console. Near-black blue base with a faint cyan blueprint grid. Light theme: none (deliberate).

## Color tokens

| Token | Value | Role |
|---|---|---|
| `--bg` | `#070b12` | page background |
| `--surface` | `#0d141f` | panels, header, footer |
| `--surface2` | `#121b2a` | hover surfaces |
| `--inset` | `#0a0f18` | inputs, wells |
| `--border` / `--border-hi` | `#1c2940` / `#2b3d5c` | hairlines / hover |
| `--cyan` | `#00d4f5` | primary accent: actions, receiver, physics estimate |
| `--amber` | `#f5b04a` | GP correction layer, fallback tags, caution |
| `--green` | `#46c97a` | healthy / confirmed route |
| `--red` | `#ff6056` | errors, storm, MUF warnings |
| `--text` | `#d2dce8` | primary text |
| `--muted` | `#7d92a8` | secondary text, labels |
| `--faint` | `#5a7089` | tertiary micro-copy (units, captions) |

Color semantics are fixed: cyan = physics/primary, amber = GP/experimental, green = confirmed/healthy, red = error/storm. Never swap.

## Typography

- `--mono` "Cascadia Code" stack: all data, numbers, labels, buttons, captions.
- `--sans` system-ui stack: body prose only (empty state, explanations).
- Base 13px; floor for micro-copy ~9.5px; uppercase reserved for short section labels and tags.

## Layout

Fixed app shell: 52px header / `352px | 1fr | 372px` three-panel workspace (inputs · map · solution) / 26px footer. Single breakpoint at 1180px stacks the panels; below ~720px header and footer compress.

## Components

- **Section label** (`.sec-lbl`): mono uppercase + hairline rule.
- **Route rows**: dot + name + condition; `armed` (cyan, predicted) vs `actual` (green, confirmed).
- **Warnings** (`.warn red|amber`): icon + prose in tinted bordered well.
- **Stat grids** (`.sgrid`, `.coord`): tiny uppercase key over mono value with unit suffix.
- **Map markers**: cyan pulse-ring circle = receiver, cyan diamond = SSL estimate, amber triangle = GP estimate, dashed amber circle = 1σ radius.

## Motion

150–250ms state transitions; draw-on hop ray (900ms expo-out); dash-flow propagation arc; pulsing health dot. Everything gated behind `prefers-reduced-motion`.
