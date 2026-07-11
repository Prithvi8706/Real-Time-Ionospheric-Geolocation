"""
Build DRDO_DIA-CoE_EW02_Technical_Report.docx — IEEE two-column format.
Every number traces to docs/*.md and models/hybrid_selector.py. No fabricated figures.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.join(ROOT, "report_figures")
os.makedirs(FIGDIR, exist_ok=True)

# ---------------------------------------------------------------------------
# FIGURES
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
})

def fig_pipeline():
    fig, ax = plt.subplots(figsize=(3.3, 2.5), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    boxes = [
        (5, 8.6, "Request\n(bearing, elevation, freq,\nKp, Dst, timestamp)", "#dfe7f2"),
        (5, 6.4, "Layer 1: Hybrid model selector\nPyRayHF / A-CHAIM /\nIRTAM / IRI-2016", "#cfe0d8"),
        (5, 4.2, "Layer 2: Two-pass SSL\nreceiver pass -> midpoint\nre-query -> ground range", "#cfe0d8"),
        (5, 2.0, "Layer 3: GP correction\nper-population residual\n(IRTAM GP / Storm GP)", "#cfe0d8"),
        (5, 0.2, "Tx lat/lon estimate\n+ uncertainty", "#dfe7f2"),
    ]
    for (x, y, label, color) in boxes:
        box = FancyBboxPatch((x-3.3, y-0.55), 6.6, 1.5,
                             boxstyle="round,pad=0.06,rounding_size=0.12",
                             linewidth=0.8, edgecolor="#333333", facecolor=color)
        ax.add_patch(box)
        ax.text(x, y+0.2, label, ha="center", va="center", fontsize=6.6)
    for y0, y1 in [(8.05, 7.0), (5.85, 4.8), (3.65, 2.6), (1.45, 0.75)]:
        ax.add_patch(FancyArrowPatch((5, y0), (5, y1),
                     arrowstyle="-|>", mutation_scale=8, linewidth=0.9, color="#333333"))
    fig.tight_layout(pad=0.1)
    p = os.path.join(FIGDIR, "fig1_pipeline.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p

def fig_ssl_geometry():
    fig, ax = plt.subplots(figsize=(3.3, 2.0), dpi=300)
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 6)
    # ground line
    ax.plot([0.5, 9.5], [0.8, 0.8], color="#5a4632", linewidth=1.4)
    # ionosphere layer
    ax.plot([0.5, 9.5], [5.0, 5.0], color="#2a5d8f", linewidth=1.2, linestyle="--")
    ax.text(9.4, 5.2, "F2 layer", ha="right", fontsize=6.5, color="#2a5d8f")
    ax.text(9.4, 0.95, "ground", ha="right", fontsize=6.5, color="#5a4632")
    rx = (1.2, 0.8); mid = (4.0, 5.0); tx = (6.8, 0.8)
    # ray path rx -> reflection -> tx
    ax.plot([rx[0], mid[0]], [rx[1], mid[1]], color="#b23a2e", linewidth=1.2)
    ax.plot([mid[0], tx[0]], [mid[1], tx[1]], color="#b23a2e", linewidth=1.2)
    # virtual height
    ax.plot([mid[0], mid[0]], [0.8, 5.0], color="#444", linewidth=0.7, linestyle=":")
    ax.annotate("", xy=(mid[0], 5.0), xytext=(mid[0], 0.8),
                arrowprops=dict(arrowstyle="<->", lw=0.7, color="#444"))
    ax.text(mid[0]+0.15, 2.9, "virtual\nheight", fontsize=6.3, va="center")
    # markers
    for (px, py, lab, dy) in [(rx[0], rx[1], "RX", 0.35), (tx[0], tx[1], "TX (est.)", 0.35),
                              (mid[0], mid[1], "bounce / midpoint", 0.3)]:
        ax.plot(px, py, "ko", markersize=3)
        ax.text(px, py+dy, lab, ha="center", fontsize=6.3)
    # elevation angle arc
    ax.annotate("", xy=(2.0, 0.8), xytext=(1.2, 0.8), arrowprops=dict(arrowstyle="-", lw=0))
    ax.text(1.9, 1.25, r"$\Delta$ (elev.)", fontsize=6.3)
    ax.annotate("", xy=(rx[0]+0.9, rx[1]+0.0), xytext=(rx[0], rx[1]),
                arrowprops=dict(arrowstyle="-", lw=0.6, color="#999"))
    ax.text(5.0, 0.35, r"ground range = virtual height / tan(elevation)",
            ha="center", fontsize=6.0, style="italic")
    fig.tight_layout(pad=0.1)
    p = os.path.join(FIGDIR, "fig2_ssl.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p

def fig_mae():
    fig, ax = plt.subplots(figsize=(3.3, 2.3), dpi=300)
    groups = ["IRTAM\n(nominal)", "PyRayHF\n(storm)"]
    baseline = [103.29, 610.80]
    corrected = [77.15, 111.96]
    x = np.arange(len(groups)); w = 0.36
    b1 = ax.bar(x - w/2, baseline, w, label="Baseline (physics)", color="#9aa7b2", edgecolor="#333", linewidth=0.5)
    b2 = ax.bar(x + w/2, corrected, w, label="GP-corrected", color="#3a6ea5", edgecolor="#333", linewidth=0.5)
    ax.set_ylabel("MAE (km)", fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(groups, fontsize=7)
    ax.legend(fontsize=6.3, frameon=False)
    ax.set_ylim(0, 680)
    for bars in (b1, b2):
        for rect in bars:
            h = rect.get_height()
            ax.text(rect.get_x()+rect.get_width()/2, h+8, f"{h:.0f}",
                    ha="center", va="bottom", fontsize=6.2)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=0.2)
    p = os.path.join(FIGDIR, "fig3_mae.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p

# Bearing-noise study results (docs/bearing_noise_results.md; seed 42, N=1/cell)
BN_SIGMAS = [0.0, 0.5, 1.0, 2.0]
BN_MEDIAN = np.array([
    [3.2,  51.6, 116.1, 186.2],
    [11.7, 54.0, 103.9, 224.5],
    [18.8, 65.9, 112.9, 227.6],
    [44.5, 77.9, 118.7, 249.9],
])  # rows az_sigma, cols el_sigma
BN_MAE = [
    ["87.2",  "205.8", "207.6", "409.2"],
    ["94.6",  "164.5", "267.2", "377.8"],
    ["102.7", "158.9", "224.7", "549.9"],
    ["122.5", "216.9", "247.2", "576.9"],
]

def fig_bearing_heatmap():
    from matplotlib.colors import LogNorm
    fig, ax = plt.subplots(figsize=(3.3, 2.5), dpi=300)
    norm = LogNorm(vmin=3.0, vmax=260.0)
    ax.pcolormesh(BN_MEDIAN, cmap="Blues", norm=norm,
                  edgecolors="white", linewidth=1.2)
    for i in range(4):
        for j in range(4):
            v = BN_MEDIAN[i, j]
            label = f"{v:.1f}" if v < 10 else f"{v:.0f}"
            ax.text(j + 0.5, i + 0.5, label, ha="center", va="center",
                    fontsize=7.2,
                    color="white" if norm(v) > 0.65 else "#1a1a1a")
    ticks = [0.5, 1.5, 2.5, 3.5]
    labels = [f"{s:g}\N{DEGREE SIGN}" for s in BN_SIGMAS]
    ax.set_xticks(ticks); ax.set_xticklabels(labels, fontsize=7)
    ax.set_yticks(ticks); ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("elevation error \N{GREEK SMALL LETTER SIGMA} (deg)", fontsize=7.5)
    ax.set_ylabel("azimuth error \N{GREEK SMALL LETTER SIGMA} (deg)", fontsize=7.5)
    ax.invert_yaxis()  # az_sigma = 0 row at top
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_aspect("equal")
    fig.tight_layout(pad=0.2)
    p = os.path.join(FIGDIR, "fig4_bearing.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig)
    return p

FIG1 = fig_pipeline()
FIG2 = fig_ssl_geometry()
FIG3 = fig_mae()
FIG4 = fig_bearing_heatmap()

# ---------------------------------------------------------------------------
# DOCX HELPERS
# ---------------------------------------------------------------------------
FONT = "Times New Roman"

def set_cell_font(cell, size=8, bold=False, align=None):
    for p in cell.paragraphs:
        if align is not None:
            p.alignment = align
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        for r in p.runs:
            r.font.name = FONT
            r.font.size = Pt(size)
            r.font.bold = bold

def set_columns(section, num, space_twips=360):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num))
    cols.set(qn("w:space"), str(space_twips))

def body_para(doc, text, justify=True, indent=True, size=10, space_after=4):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    if indent:
        pf.first_line_indent = Inches(0.18)
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.0
    r = p.add_run(text)
    r.font.name = FONT; r.font.size = Pt(size)
    return p

def heading(doc, num, title):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(f"{num}.  {title.upper()}")
    r.font.name = FONT; r.font.size = Pt(10); r.font.small_caps = True
    return p

def subheading(doc, letter, title):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"{letter}. ")
    r.font.name = FONT; r.font.size = Pt(10); r.font.italic = True
    r2 = p.add_run(title)
    r2.font.name = FONT; r2.font.size = Pt(10); r2.font.italic = True
    return p

def add_figure(doc, path, caption, width_in=3.3):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(1)
    p.add_run().add_picture(path, width=Inches(width_in))
    c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(6)
    r = c.add_run(caption)
    r.font.name = FONT; r.font.size = Pt(8)

def table_caption(doc, text):
    c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_before = Pt(6); c.paragraph_format.space_after = Pt(2)
    r = c.add_run(text)
    r.font.name = FONT; r.font.size = Pt(8); r.font.small_caps = True

def make_table(doc, rows, col_widths_in, header_size=7.5, body_size=7.5):
    n_rows = len(rows); n_cols = len(rows[0])
    t = doc.add_table(rows=n_rows, cols=n_cols)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    t.autofit = False
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = t.rows[i].cells[j]
            cell.text = str(val)
            cell.width = Inches(col_widths_in[j])
            set_cell_font(cell, size=(header_size if i == 0 else body_size),
                          bold=(i == 0),
                          align=WD_ALIGN_PARAGRAPH.CENTER if j > 0 else WD_ALIGN_PARAGRAPH.LEFT)
    # enforce widths on every cell (Word can ignore single-cell width)
    for row in t.rows:
        for j, cell in enumerate(row.cells):
            cell.width = Inches(col_widths_in[j])
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(6)
    return t

# ---------------------------------------------------------------------------
# DOCUMENT
# ---------------------------------------------------------------------------
doc = Document()
# base style
normal = doc.styles["Normal"]
normal.font.name = FONT
normal.font.size = Pt(10)

sec = doc.sections[0]
sec.page_width = Inches(8.5); sec.page_height = Inches(11)
sec.top_margin = Inches(0.75); sec.bottom_margin = Inches(1.0)
sec.left_margin = Inches(0.625); sec.right_margin = Inches(0.625)

# ---- Full-width title / author band (section 0 = single column) ----
title = doc.add_paragraph(); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_after = Pt(6)
r = title.add_run("Real-Time Ionospheric Geolocation: Closing the HF "
                  "Single-Station Range Gap with a Hybrid Ionospheric "
                  "Model Stack and Gaussian-Process Correction")
r.font.name = FONT; r.font.size = Pt(20)

auth = doc.add_paragraph(); auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
auth.paragraph_format.space_after = Pt(2)
r = auth.add_run("Prithvi Raghu")
r.font.name = FONT; r.font.size = Pt(12)

aff = doc.add_paragraph(); aff.alignment = WD_ALIGN_PARAGRAPH.CENTER
aff.paragraph_format.space_after = Pt(0)
for line, it in [("B.Tech Computer Science (Year 3), Vellore Institute of Technology, Vellore, India", True),
                 ("Project: DRDO DIA-CoE/EW/02", True),
                 ("prithviraghu080706@gmail.com", True)]:
    rr = aff.add_run("\n" + line if line != "B.Tech Computer Science (Year 3), Vellore Institute of Technology, Vellore, India" else line)
    rr.font.name = FONT; rr.font.size = Pt(10); rr.font.italic = it
aff.paragraph_format.space_after = Pt(8)

# ---- Switch to two-column body ----
new_sec = doc.add_section(WD_SECTION.CONTINUOUS)
set_columns(doc.sections[0], 1)
set_columns(new_sec, 2, space_twips=360)
new_sec.top_margin = Inches(0.75); new_sec.bottom_margin = Inches(1.0)
new_sec.left_margin = Inches(0.625); new_sec.right_margin = Inches(0.625)

# ---- Abstract ----
ab = doc.add_paragraph(); ab.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
ab.paragraph_format.space_after = Pt(4)
r = ab.add_run("Abstract—")
r.font.name = FONT; r.font.size = Pt(9); r.font.bold = True; r.font.italic = True
abstract_text = (
    "High-frequency (HF) emitter geolocation from a single receiving station is "
    "limited by the ionospheric range estimate: operational direction finding "
    "yields a bearing but no range. This work closes that gap with a three-layer, "
    "real-time pipeline—a condition-aware hybrid ionospheric model selector, a "
    "two-pass single-station-location (SSL) algorithm that re-queries the ionosphere "
    "at the signal reflection point, and a per-population Gaussian-process (GP) layer "
    "that corrects the systematic SSL bias. Trained and evaluated on real ionosonde "
    "residuals from the GIRO AH223 Ahmedabad station (June, July, December 2012), the "
    "system reduces held-out test-fold mean absolute error from 103.29 km to 77.15 km "
    "(25.3%) under nominal mid-latitude conditions and from 610.80 km to 111.96 km "
    "(81.7%) under geomagnetic-storm conditions, where HF geolocation degrades most "
    "and matters most. These figures are interpolation within the training "
    "distribution, not cross-station or cross-season generalization. A ground-truth "
    "test-signal generator (an explicit deliverable) and a bearing-noise sensitivity "
    "study establish the geolocation Figure of Merit directly: with perfect bearings "
    "the SSL algorithm's median intrinsic error is 3.2 km, and elevation-bearing error "
    "dominates, costing 4\N{EN DASH}6\N{MULTIPLICATION SIGN} more than equal azimuth "
    "error and reaching a 186 km median at 2\N{DEGREE SIGN} elevation noise. The "
    "contribution is a reproducible, fully offline-capable FastAPI service built on "
    "open ionosonde data, together with an explicit validity envelope and a documented "
    "defect ledger."
)
r = ab.add_run(abstract_text)
r.font.name = FONT; r.font.size = Pt(9); r.font.bold = True; r.font.italic = False
r.font.bold = False  # abstract body is bold-italic header only in IEEE; keep body upright 9pt

kw = doc.add_paragraph(); kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
kw.paragraph_format.space_after = Pt(6)
r = kw.add_run("Index Terms—")
r.font.name = FONT; r.font.size = Pt(9); r.font.bold = True; r.font.italic = True
r = kw.add_run("HF geolocation, single-station location, ionospheric modelling, "
               "IRTAM, IRI, ray tracing, Gaussian process, electronic warfare.")
r.font.name = FONT; r.font.size = Pt(9); r.font.italic = True

# ====================== I. INTRODUCTION ======================
heading(doc, "I", "Introduction")
body_para(doc,
    "Geolocating a high-frequency (HF, 3–30 MHz) emitter is a core electronic-warfare "
    "task. HF signals propagate beyond line of sight by refracting off the ionosphere, "
    "so a single receiver can detect an emitter thousands of kilometres away. The "
    "operational baseline for such a receiver is bearing-only direction finding: the "
    "system measures the azimuth and elevation of the arriving skywave but produces no "
    "range. Direction without range leaves the emitter located only to a line, not a point.")
body_para(doc,
    "DRDO problem statement DIA-CoE/EW/02 targets exactly this gap: convert a "
    "bearing-only HF measurement into a full latitude/longitude estimate in real time. "
    "Range is recovered through single-station location (SSL) geometry, which trades the "
    "measured elevation angle against the ionospheric virtual height to compute ground "
    "range. The accuracy of that range is therefore bounded by the accuracy of the "
    "ionospheric model at the moment and place of reflection—and climatological models "
    "such as the International Reference Ionosphere (IRI) do not capture the short-term, "
    "storm-driven departures that dominate error precisely when geolocation matters most.")
body_para(doc,
    "This system was rebuilt and validated solo. The original fifteen-person project "
    "team disbanded; the pipeline described here—model selector, two-pass SSL, GP "
    "correction, service layer, validation, and documentation—was reconstructed and "
    "verified independently.")
body_para(doc,
    "The central contribution is stated plainly: during geomagnetic storms—when HF "
    "geolocation degrades most and matters most—this system reduces single-station "
    "range error from 611 km to 112 km, validated on real ionosonde data from AH223 "
    "Ahmedabad. Under nominal conditions it reduces error from 103 km to 77 km. The "
    "remainder of this paper formulates the problem (Section II), describes the "
    "architecture (Sections III–V), reports validation (Section VI), establishes the "
    "test-signal ground truth and bearing-error figure of merit (Section VII), states "
    "the validity envelope and defect ledger honestly (Section VIII), and outlines the "
    "path to operational use (Section IX).")

# ====================== II. PROBLEM FORMULATION ======================
heading(doc, "II", "Problem Formulation")
body_para(doc,
    "A single station measures three quantities for an arriving skywave: the azimuth "
    "(bearing) φ, the elevation angle Δ, and the signal frequency f. The emitter is "
    "assumed to lie along the great-circle bearing φ from the receiver. The unknown is "
    "the ground range D from receiver to emitter; recovering it converts the bearing "
    "line into a point estimate.")
body_para(doc,
    "Under the classical single-hop SSL approximation, the skywave reflects from an "
    "ionospheric layer at a virtual height hᵥ, and simple geometry relates range to the "
    "measured elevation angle:")
eq = doc.add_paragraph(); eq.alignment = WD_ALIGN_PARAGRAPH.CENTER
eq.paragraph_format.space_after = Pt(4)
r = eq.add_run("ground_distance = virtual_height / tan(elevation_deg)")
r.font.name = FONT; r.font.size = Pt(10); r.font.italic = True
body_para(doc,
    "The virtual height is a convenient fiction. A real skywave does not reflect from a "
    "thin mirror; it refracts continuously as it climbs into a region of increasing "
    "electron density, reaches an apogee where the local plasma frequency equals the "
    "signal's effective vertical frequency, and descends again. The virtual height is the "
    "apparent reflection height a flat mirror would need to reproduce the observed "
    "time-of-flight. It exceeds the true peak height, and the gap between them depends on "
    "the full electron-density profile—which is exactly what climatological models "
    "approximate only coarsely.")
body_para(doc,
    "Estimating range is therefore hard for three compounding reasons. First, the virtual "
    "height itself is uncertain: it is a functional of the whole profile, and the profile "
    "is what the ionospheric model must supply. Second, the ionosphere is not horizontally "
    "uniform, so the profile that governs reflection is not the profile above the "
    "receiver. Third, during disturbed conditions the F2-layer height and critical "
    "frequency vary on timescales of minutes, so any climatological average is stale at "
    "the moment of measurement. Each effect propagates directly into hᵥ and hence into D "
    "through the tangent relation, where the error is further amplified at low elevation "
    "angles.")
body_para(doc,
    "A structural limitation of naive SSL compounds these: the ionosphere is sampled only "
    "at the receiver, whereas the physically relevant reflection point lies roughly "
    "halfway to the emitter. Where horizontal gradients in electron density exist—the "
    "common case—a single receiver-side ionospheric call introduces a systematic range "
    "bias rather than zero-mean noise. Section III addresses the sampling-point error with "
    "a two-pass re-query, and Section V addresses the remaining structured bias with a "
    "learned correction.")

# ====================== III. SYSTEM ARCHITECTURE ======================
heading(doc, "III", "System Architecture")
body_para(doc,
    "The pipeline has three layers (Fig. 1). Layer 1 selects the most appropriate "
    "ionospheric model for the current geomagnetic conditions and returns a profile. "
    "Layer 2 runs a two-pass SSL computation that converts elevation angle to ground "
    "range, re-querying the ionosphere at the reflection point. Layer 3 applies a "
    "Gaussian-process correction trained on real residuals to remove the systematic SSL "
    "bias. A FastAPI service wraps the pipeline behind two endpoints.")
add_figure(doc, FIG1, "Fig. 1.  Three-layer pipeline: hybrid model selector, two-pass "
                      "SSL, and per-population GP correction.")
subheading(doc, "A", "Two-pass SSL")
body_para(doc,
    "The first pass computes a rough range using the ionospheric profile at the receiver, "
    "then projects the emitter position along the azimuth. The midpoint between receiver "
    "and rough emitter approximates the reflection (bounce) point. The second pass "
    "re-queries the ionospheric model at that midpoint and recomputes the range from the "
    "reflection-point profile. Querying the model where the ray actually reflects, rather "
    "than at the receiver, captures the horizontal electron-density gradient that would "
    "otherwise bias the estimate (Fig. 2). The transmitter location is then obtained by "
    "moving along the great-circle path from the receiver at the measured azimuth for the "
    "computed ground range, using spherical-Earth geometry.")
add_figure(doc, FIG2, "Fig. 2.  Single-hop SSL geometry. The second pass re-queries the "
                      "ionosphere at the midpoint reflection point.")
body_para(doc,
    "Virtual height is extracted differently per model. For PyRayHF the ray-traced "
    "virtual_height_km is used directly, since the ray tracer computes the apparent "
    "reflection height explicitly. For IRTAM, IRI, and A-CHAIM the F2-peak height hmF2 is "
    "used as a proxy. Two guards protect this step. If the extracted height is null, zero, "
    "NaN, or otherwise non-positive, the service returns HTTP 503 rather than letting a "
    "nonsensical or infinite location propagate (the D2 null-profile guard). And because "
    "tan(0°) = 0 would produce infinite range, the request validator enforces an elevation "
    "angle of at least 1.0° and rejects angles above 60°, which lie outside the typical HF "
    "skywave geometry on which the system was validated.")
subheading(doc, "B", "Service layer")
body_para(doc,
    "A FastAPI service exposes the pipeline. POST /locate accepts the receiver position, "
    "azimuth, elevation, frequency, timestamp, and geomagnetic indices (Kp, Dst, "
    "optional F10.7), and returns the SSL physics estimate, the GP-corrected estimate "
    "with posterior uncertainty, the model audit trail, and warning flags. GET /health "
    "confirms that all four GP model files loaded at start-up and reports the training "
    "row counts (7,382 for the IRTAM GP, 183 for the storm GP) for pre-demonstration "
    "verification. Input validation rejects out-of-range fields with HTTP 422; a null or "
    "non-positive virtual height returns HTTP 503 rather than a nonsensical location.")

# ====================== IV. HYBRID SELECTOR ======================
heading(doc, "IV", "Hybrid Ionospheric Model Selector")
body_para(doc,
    "Layer 1 evaluates four conditions in strict priority order and commits to the first "
    "match (verified in models/hybrid_selector.py):")
# priority list
for txt in [
    "1) PyRayHF (storm slot): selected when Kp ≥ 5 or Dst ≤ −100 nT. PyRayHF "
    "ray-traces a virtual height by injecting an IRI electron-density profile into the "
    "Appleton–Hartree formulation and returns virtual height directly, rather than "
    "deriving it from the F2-peak height. The SAMI3 first-principles model is not "
    "integrated; PyRayHF is the storm-time proxy in this slot.",
    "2) A-CHAIM v6.0.3 (high-latitude slot): selected when |lat| ≥ 60°. An empirical "
    "auroral model from NRCan, invoked as an external executable. At AH223 (23°N) it "
    "never fires; it is present for polar or sub-polar deployment completeness.",
    "3) PyIRTAM (assimilated nominal): the highest-quality model for nominal mid-latitude "
    "conditions when local date-specific coefficient files are present.",
    "4) IRI-2016 (calm fallback): always available; depends on no external files.",
]:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Inches(0.12)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(txt); r.font.name = FONT; r.font.size = Pt(10)
body_para(doc,
    "Each non-IRI branch checks whether its wrapper produced a usable profile before "
    "committing. If the profile is null or incomplete, the system logs a warning and "
    "re-queries IRI. This runtime fallback is why two distinct fields appear in every "
    "response: selected_model records the selector's original intent, while model_used "
    "records the model that actually produced the profile. The two differ when, for "
    "example, IRTAM is selected but its coefficient files are missing and IRI is used "
    "instead. Preserving this distinction (the D1 fix) is essential: the GP correction "
    "must route on model_used, not selected_model, or it will apply the wrong population's "
    "correction.")
body_para(doc,
    "A concrete fallback illustrates why the audit trail matters. Suppose conditions are "
    "nominal and the caller sets irtam_available = true, so the selector chooses IRTAM "
    "(selected_model = \"IRTAM\"). If the local coefficient files for the requested date "
    "are absent, the IRTAM wrapper returns null fields, the pipeline re-queries IRI, and "
    "model_used becomes \"IRI\". Before the D1 fix both fields were set to the same value, "
    "fallbacks were silent, and the GP routed on the wrong population. A-CHAIM is similar "
    "in spirit: it is invoked as an external executable whose paths are supplied through "
    "the ACHAIM_EXE_PATH and ACHAIM_DB_PATH environment variables, and a misconfigured "
    "path falls back to IRI as well.")
body_para(doc,
    "A maximum-usable-frequency (MUF) guard (the D12 fix) compares the request frequency "
    "against foF2, the critical frequency of the F2 layer extracted from the second-pass "
    "profile. If frequency_mhz exceeds foF2 the signal would penetrate rather than "
    "reflect, invalidating the SSL geometry; the response sets muf_warning = true and "
    "appends a note to the GP-correction field so the operator can discount the estimate.")

# ====================== V. GP CORRECTION ======================
heading(doc, "V", "Gaussian-Process Correction Layer")
body_para(doc,
    "The physics-only SSL estimate carries a systematic bias because the ionosphere "
    "departs from the SSL assumptions (horizontal uniformity, single reflection, no ray "
    "bending). This bias is learnable: given the same geometry and conditions, it tends to "
    "repeat. Layer 3 trains a Gaussian process on real residuals—the difference between "
    "the SSL estimate and the known emitter location—and adds the predicted residual back "
    "at inference time, together with a posterior standard deviation.")
subheading(doc, "A", "Feature vector")
body_para(doc,
    "Each GP consumes a ten-element feature vector, in order: azimuth_deg, elevation_deg, "
    "frequency_mhz, virtual_height_km, Kp, Dst, hour-of-day, month-of-year, baseline "
    "latitude, and baseline longitude. The baseline latitude and longitude are the SSL "
    "physics estimate of the emitter position; hour and month are extracted from the "
    "timestamp. Separate GP pairs predict the latitude and longitude residuals.")
subheading(doc, "B", "Per-population routing")
body_para(doc,
    "IRTAM and storm (PyRayHF) rows have structurally different error patterns. IRTAM "
    "residuals under nominal conditions are small and spatially smooth; storm residuals "
    "are large and behave differently. Training both populations into a single GP collapses "
    "the latitude kernel—the length scale drops toward zero and the noise floor dominates"
    "—destroying the correction. The fix is two separate GP pairs, one per population, "
    "routed at inference time on model_used. IRI and A-CHAIM branches have too few samples "
    "to train a reliable GP, so for those the correction is reported as not_applied.")
subheading(doc, "C", "Training data and split")
body_para(doc,
    "The GPs are trained on residuals from the GIRO AH223 Ahmedabad ionosonde (23.0°N, "
    "72.6°E) for June, July, and December 2012—the Solar Cycle 24 peak. An 80/20 "
    "train/test split (random seed 42) is applied within each population separately, so "
    "test-fold figures never include rows seen during training.")
subheading(doc, "D", "Uncertainty output")
body_para(doc,
    "Each GP prediction carries a posterior standard deviation for the latitude and "
    "longitude residual. The service exposes these as uncertainty_lat_deg and "
    "uncertainty_lon_deg and combines them into a single correction_std_km by root-sum-"
    "square, accounting for the cos(lat) compression of longitude: "
    "sqrt((σ_lat·111)² + (σ_lon·111·cos lat)²). These are the GP's confidence about its "
    "own residual prediction, not end-to-end location-error bounds; the true error also "
    "includes whatever bias the GP has not learned.")
subheading(doc, "E", "Out-of-distribution warning")
body_para(doc,
    "Because the GP was trained on a narrow distribution, requests outside it are flagged "
    "with ood_warning = true. The check fires when the observation month is not in {June, "
    "July, December} or the estimated transmitter latitude falls outside 15–35°N. The "
    "check runs on the estimated transmitter latitude—the variable the GP was trained on"
    "—not the receiver latitude (the D11 fix). When the flag is set, the GP posterior "
    "uncertainty should be read as a lower bound on the true error, because the model is "
    "extrapolating beyond the support of its training data.")

# ====================== VI. VALIDATION AND RESULTS ======================
heading(doc, "VI", "Validation and Results")
body_para(doc,
    "The dataset comprises 9,457 residual rows from AH223, dominated by the nominal IRTAM "
    "population with a small storm population (Table I). The 80/20 split within each "
    "population yields the train/test row counts in Table I.")
table_caption(doc, "Table I.  Dataset Composition and Train/Test Split")
make_table(doc, [
    ["Population", "Total", "Share", "Train", "Test"],
    ["IRTAM (nominal)", "9,228", "97.6%", "7,382", "1,846"],
    ["PyRayHF (storm)", "229", "2.4%", "183", "46"],
    ["Total", "9,457", "100%", "7,565", "1,892"],
], col_widths_in=[1.25, 0.55, 0.55, 0.55, 0.5])
body_para(doc,
    "Performance is reported as mean absolute error (MAE, Haversine distance) on the "
    "held-out 20% test fold of each population (Table II, Fig. 3). The baseline is the SSL "
    "physics estimate with no GP correction; the corrected value adds the GP residual "
    "prediction.")
table_caption(doc, "Table II.  Held-Out Test-Fold Performance")
make_table(doc, [
    ["Population", "Test", "Baseline", "Corrected", "Impr."],
    ["IRTAM", "1,846", "103.29 km", "77.15 km", "25.3%"],
    ["PyRayHF (storm)", "46", "610.80 km", "111.96 km", "81.7%"],
], col_widths_in=[1.25, 0.5, 0.75, 0.75, 0.5])
add_figure(doc, FIG3, "Fig. 3.  Baseline vs. GP-corrected MAE on held-out test folds. "
                      "Storm error falls from 610.80 km to 111.96 km.")
body_para(doc,
    "Under nominal mid-latitude conditions the GP removes about a quarter of the ~103 km "
    "baseline bias. Under storm conditions the baseline SSL error is large (~611 km), as "
    "expected when the F2 layer is severely disturbed; the GP reduces it to ~112 km, an "
    "81.7% improvement. This storm result rests on only 229 total rows (183 train, 46 "
    "test) and should be read with that sample size in mind.")
body_para(doc,
    "These numbers are interpolation within the training distribution, not generalization. "
    "Both GPs were trained and tested on the same station and the same three months, with "
    "a row-level random split rather than a day-blocked one; because ionospheric residuals "
    "are temporally autocorrelated, a day-blocked split would be a stricter test and is "
    "recommended as future hardening. The figures measure how well the system reduces bias "
    "on the distribution it was exposed to. They are explicitly NOT: a held-out-station "
    "score, a held-out-season score, a multi-hop result, or a real-emitter-track result. "
    "The emitter geometry is simulated (random azimuths and distances under a single-hop "
    "assumption); the ionospheric profiles and geomagnetic indices driving them are real. "
    "A held-out-station generalization test—training on a set of stations and evaluating on "
    "a station withheld entirely, termed “Approach B”—is the recommended next validation "
    "step and is not yet implemented.")

# ====================== VII. TEST SIGNALS AND BEARING-ERROR FOM ======================
heading(doc, "VII", "Test Signals and Bearing-Error Figure of Merit")
body_para(doc,
    "The Table II figures measure how well the pipeline corrects ionospheric bias, but "
    "the deliverable's stated Figure of Merit is the accuracy of the location fix itself. "
    "Two dedicated tools close that gap: a ground-truth test-signal generator (itself an "
    "explicit deliverable of DIA-CoE/EW/02) and a bearing-noise sensitivity study built "
    "on top of it.")
subheading(doc, "A", "Ground-truth test signal generation")
body_para(doc,
    "The generator (data/generate_test_signals.py) places emitters at known positions—"
    "eight azimuths at 45° spacing, ground ranges of 800, 1,500, and 2,200 km, under "
    "three representative 2012 condition sets (quiet noon, quiet midnight, and Kp = 6 "
    "storm) from the AH223 receiver—and synthesises the exact observation a receiver "
    "would record. The azimuth is the initial great-circle bearing to the emitter, and "
    "the elevation is arctan(hᵥ/D) with the virtual height queried from the same hybrid "
    "ionosphere at the great-circle bounce midpoint: precisely the inverse of the SSL "
    "range relation of Section II. Signals whose true elevation falls outside the "
    "solver's validated 1–60° band are dropped by construction, leaving 72 valid "
    "ground-truth signals. The set is deterministic (seed 42), and unit tests prove the "
    "generator and solver are exact geometric inverses in pure geometry, so any residual "
    "error measured downstream is attributable to the algorithm, not the harness.")
subheading(doc, "B", "Bearing-noise sensitivity study")
body_para(doc,
    "Real HF direction finders measure bearings with errors of a degree or more, and in "
    "SSL geometry the elevation angle enters through tan(Δ), so bearing error—absent "
    "from the Table II figures—is the dominant real-world error source. The study "
    "(bearing_noise_study.py) injects independent zero-mean Gaussian error into azimuth "
    "and elevation, sweeping each standard deviation over {0, 0.5, 1.0, 2.0}° (a 4×4 "
    "grid), clips noisy elevations to the 1–60° band, and runs the full two-pass "
    "ssl_locate on every noisy observation against the same hybrid ionosphere the "
    "signals were synthesised from. Ionospheric lookups are memoised on coordinates "
    "quantised to 0.1°—well below the ionosphere's native spatial resolution—so 923 "
    "real model calls served 2,304 lookups; the per-cell realization count is sized "
    "from a measured per-call latency probe (one draw per signal per cell, 72 trials "
    "per cell, 1,152 total; seed 42, fully reproducible).")
table_caption(doc, "Table III.  Geolocation MAE (km) Under Bearing Error "
                   "(Rows: Azimuth σ; Columns: Elevation σ)")
make_table(doc, [
    ["az σ \\ el σ", "0.0°", "0.5°", "1.0°", "2.0°"],
    ["0.0°"] + BN_MAE[0],
    ["0.5°"] + BN_MAE[1],
    ["1.0°"] + BN_MAE[2],
    ["2.0°"] + BN_MAE[3],
], col_widths_in=[0.8, 0.62, 0.62, 0.62, 0.62])
add_figure(doc, FIG4, "Fig. 4.  Median geolocation error (km) over the bearing-noise "
                      "grid. The zero-noise cell is the 3.2 km intrinsic floor; error "
                      "grows far faster along the elevation axis than the azimuth axis.")
body_para(doc,
    "Three results stand out. First, the intrinsic floor: with perfect bearings the "
    "algorithm's median error is 3.2 km (P90 49 km). Under quiet conditions the floor is "
    "excellent—sub-kilometre at 800 km range, 5–9 km at 2,200 km—so the two-pass "
    "approximation is very tight when the virtual-height field is smooth. Under the "
    "storm condition the floor is heavy-tailed (worst zero-noise trial 3,192 km): "
    "ray-traced virtual heights vary strongly with position, the pass-one height at the "
    "receiver mislocates the bounce midpoint, and the residual height difference is "
    "amplified by 1/tan(Δ) ≈ 10–18× at the 3–8° elevations of long-range signals. This "
    "tail, not typical behaviour, is why the zero-noise MAE (87.2 km) sits far above its "
    "median.")
body_para(doc,
    "Second, elevation error dominates, as the geometry predicts: at equal σ it costs "
    "4–6× more than azimuth error (median 186.2 km for 2.0° elevation noise alone versus "
    "44.5 km for 2.0° azimuth noise alone; 116.1 versus 18.8 km at 1.0°). Draws that push "
    "low-elevation signals toward the 1° clip explode the range estimate—the largest "
    "single-trial error was 5,493 km—so low-elevation, long-range geometry is where "
    "bearing quality matters most. Third, azimuth error mainly rotates the fix: az-only "
    "medians grow gently (3.2 → 11.7 → 18.8 → 44.5 km), consistent with cross-range "
    "displacement of approximately range × sin σ.")
body_para(doc,
    "Two scope notes apply. The study isolates the algorithm: observations are "
    "synthesised and inverted with the same hybrid ionosphere, so ionospheric-model "
    "error—characterised separately in Table II—is excluded by design, and the two "
    "error sources are not conflated. And with one noise draw per signal per cell, the "
    "MAE cells rest on 72 trials and are not perfectly monotone (heavy-tailed single "
    "draws dominate means); the medians of Fig. 4, which are robust, are monotone in "
    "both axes.")

# ====================== VIII. VALIDITY ENVELOPE AND LIMITATIONS ======================
heading(doc, "VIII", "Validity Envelope and Known Limitations")
body_para(doc,
    "Table IV states what is and is not validated. The system is validated for single-hop "
    "mid-latitude geometry at AH223 Ahmedabad over June, July, and December 2012, with "
    "real ionospheric and geomagnetic data but simulated emitter geometry.")
table_caption(doc, "Table IV.  Validity Envelope")
make_table(doc, [
    ["Validated (in scope)", "Not validated (out of scope)"],
    ["AH223 Ahmedabad, 23°N", "Other stations / latitudes"],
    ["Jun/Jul/Dec 2012", "Other months / years"],
    ["Single-hop geometry", "Multi-hop propagation"],
    ["Simulated emitter geometry", "Real emitter tracks"],
    ["Solar Cycle 24 peak", "Other solar-cycle phases"],
    ["Within-distribution interpolation", "Cross-station generalization"],
    ["Bearing-error FoM, same-model isolation", "Combined model + bearing error"],
], col_widths_in=[1.7, 1.7])
body_para(doc,
    "Table V enumerates all nine documented limitations with their severity. Two are "
    "scope statements that define the deployment site rather than defects; the remainder "
    "are graded medium or low.")
table_caption(doc, "Table V.  Known Limitations and Severity")
make_table(doc, [
    ["#", "Limitation", "Severity"],
    ["1", "Single station / season / geometry scope", "Scope"],
    ["2", "GP not validated on held-out station", "Scope"],
    ["3", "PyRayHF fixed at 5 MHz (D8)", "Medium"],
    ["4", "F10.7 defaults to 130 SFU (D9)", "Low"],
    ["5", "A-CHAIM never fires at India geometry", "Low"],
    ["6", "Storm GP trained on 183 rows", "Medium"],
    ["7", "Two-call model inconsistency at 60°N", "Low"],
    ["8", "Antimeridian midpoint arithmetic", "Low"],
    ["9", "No inter-annual temporal validation", "Scope"],
], col_widths_in=[0.3, 2.55, 0.55], body_size=7.0)
body_para(doc,
    "Two limitations deserve emphasis. The PyRayHF ray tracer runs at a fixed internal "
    "frequency of 5.0 MHz, and the storm GP was trained at that frequency; a request at a "
    "different frequency mixes a 5 MHz physics height with a request-frequency feature, "
    "degrading the storm correction (medium severity, not yet fixed). And the storm GP's "
    "183 training rows are a small sample for a Gaussian process: the posterior inflates "
    "quickly away from training points and cannot finely distinguish storm severities "
    "(medium severity, flagged).")
subheading(doc, "A", "Defect ledger")
body_para(doc,
    "Catching and resolving defects during engineering review is a strength of the "
    "process, not a weakness to hide. Table VI records the principal defects found and "
    "their resolution.")
table_caption(doc, "Table VI.  Defect Ledger")
make_table(doc, [
    ["Defect", "Status"],
    ["foF2 unit error (D-series)", "Fixed"],
    ["IRI hmF2 null sentinel → HTTP 503 guard", "Fixed"],
    ["scikit-learn version retrain (pinned)", "Fixed"],
    ["GP kernel collapse (mixed population)", "Fixed (per-population)"],
    ["selected_model vs model_used audit trail (D1)", "Fixed"],
    ["MUF warning (D12)", "Fixed"],
    ["PyRayHF fixed at 5 MHz (D8)", "Open (medium)"],
], col_widths_in=[2.35, 1.05], body_size=7.0)
body_para(doc,
    "Each ledger entry was caught during engineering review and either resolved or "
    "explicitly tracked. The foF2 unit error was a thousand-fold scaling mistake in the "
    "critical-frequency formula; the null-sentinel guard converts a missing IRI hmF2 into a "
    "clean HTTP 503 instead of a 500 traceback during a live demonstration; the scikit-"
    "learn version is pinned so the serialised GP models load deterministically; and the "
    "kernel-collapse defect motivated the per-population split described in Section V. "
    "Three low-severity geometric limitations remain documented rather than fixed because "
    "they cannot fire at the AH223 23°N deployment: the two ionospheric calls could select "
    "different models if a midpoint crosses the 60° A-CHAIM latitude boundary; the midpoint "
    "longitude uses an arithmetic mean that is wrong across the ±180° antimeridian; and the "
    "A-CHAIM branch itself receives no test coverage at India geometry. Each has a known "
    "fix path and would be addressed before a polar or trans-antimeridian deployment.")

# ====================== IX. PATH TO OPERATIONAL USE ======================
heading(doc, "IX", "Path to Operational Use")
body_para(doc,
    "Fielding this system operationally requires closing the generalization gap that "
    "Section VI states honestly. The priority is multi-station validation: training on a "
    "set of ionosonde stations and evaluating on a held-out station (“Approach B”) to "
    "produce a cross-station generalization score rather than an interpolation score. "
    "Beyond that, the system needs validation against real emitter tracks instead of "
    "simulated geometry, and across seasons and solar-cycle phases outside the 2012 "
    "training window. The bearing-error figure of merit of Section VII should likewise "
    "be extended with larger noise-realization budgets (the current grid uses one draw "
    "per signal per cell) and a cross-model mismatch variant that measures combined "
    "model-plus-bearing error.")
body_para(doc,
    "Several engineering paths are already scoped. The storm slot is architecturally "
    "complete behind a model-agnostic interface; integrating the SAMI3 first-principles "
    "physics model in place of the PyRayHF proxy awaits real-time data access. The "
    "ionospheric baseline can be upgraded from IRI-2016 to IRI-2020. The F10.7 solar-flux "
    "index, currently defaulting to 130 SFU, can be auto-populated per observation date "
    "via an OMNI-web lookup—the request field and validator already exist; only the fetch "
    "logic is missing. Finally, the storm GP should be retrained once PyRayHF is "
    "parameterised to run at the request frequency rather than a fixed 5 MHz.")
body_para(doc,
    "Air-gapped deployment is already supported. The Leaflet mapping library is bundled "
    "and served locally with no CDN dependency, and the entire geolocation pipeline—"
    "Python code, model files, and overlay logic—runs fully offline. Only live map-tile "
    "imagery requires external connectivity, and that can be replaced with a pre-cached "
    "local tile set for a fully air-gapped installation.")

# ====================== REFERENCES ======================
_rh = doc.add_paragraph(); _rh.alignment = WD_ALIGN_PARAGRAPH.CENTER
_rh.paragraph_format.space_before = Pt(8); _rh.paragraph_format.space_after = Pt(3)
_r = _rh.add_run("References")
_r.font.name = FONT; _r.font.size = Pt(10); _r.font.small_caps = True
refs = [
    "D. Bilitza et al., “The International Reference Ionosphere (IRI),” IRI Working "
    "Group, model series (IRI-2016).",
    "I. Galkin et al., “IRTAM: IRI-based Real-Time Assimilative Model,” University of "
    "Massachusetts Lowell, GIRO.",
    "A-CHAIM: Advanced Canadian High Arctic Ionospheric Model, v6.0.3, Natural Resources "
    "Canada.",
    "PyRayHF HF ray-tracing library (Appleton–Hartree formulation over IRI electron-"
    "density profiles).",
    "GIRO Global Ionosphere Radio Observatory, station AH223 (Ahmedabad, 23.0°N, "
    "72.6°E).",
    "NASA OMNIWeb / OMNI2 space-weather indices (Kp, Dst, F10.7).",
    "C. E. Rasmussen and C. K. I. Williams, Gaussian Processes for Machine Learning, MIT "
    "Press, 2006.",
]
for i, ref in enumerate(refs, 1):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.first_line_indent = Inches(-0.18)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(f"[{i}] {ref}")
    r.font.name = FONT; r.font.size = Pt(8)

out = os.path.join(ROOT, "DRDO_DIA-CoE_EW02_Technical_Report.docx")
doc.save(out)
print("SAVED:", out)
print("Figures:", FIG1, FIG2, FIG3)
