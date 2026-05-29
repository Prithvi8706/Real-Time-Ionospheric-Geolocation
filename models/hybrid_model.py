import os
from datetime import datetime
from models.hybrid_selector import select_model, SelectionResult
from models.iri.iri_wrapper import get_iri_profile, IRIProfile
from models.achaim.achaim_wrapper import get_achaim_profile
from models.irtam.irtam_wrapper import get_irtam_profile, is_irtam_available
from models.rayhf.rayhf_wrapper import get_rayhf_profile, is_rayhf_available
import logging

logger = logging.getLogger(__name__)

# ── A-CHAIM config (Issue 5 fix: env vars replace hardcoded paths) ───────────
# Set ACHAIM_EXE_PATH and ACHAIM_DB_PATH in your environment before running.
# Example (PowerShell):
#   $env:ACHAIM_EXE_PATH = "C:\path\to\A-CHAIM\ACHAIM.exe"
#   $env:ACHAIM_DB_PATH  = "C:\path\to\A-CHAIM\example.db"
# A-CHAIM is only invoked for |lat| >= 60 — mid-latitude demos never trigger it.
ACHAIM_EXE_PATH = os.environ.get(
    "ACHAIM_EXE_PATH",
    "C:/Users/prith/Downloads/A-CHAIM_User_Release-6.0.3/A-CHAIM_User_Release-6.0.3/C/ACHAIM/ACHAIM.exe"
)
ACHAIM_DB_PATH = os.environ.get(
    "ACHAIM_DB_PATH",
    "C:/Users/prith/Downloads/A-CHAIM_User_Release-6.0.3/A-CHAIM_User_Release-6.0.3/C/example/example.db"
)


def get_ionosphere(
    lat: float,
    lon: float,
    dt: datetime,
    kp: float,
    dst: float,
    irtam_available: bool = False
) -> dict:
    """
    Master function — selects the right model and returns ionospheric profile.

    Returns a dict with:
      - model_used: actual model that produced the profile (may differ from
                    selected_model if a fallback occurred)
      - selected_model: model that was attempted (audit trail)
      - reason: why that model was chosen
      - profile: IRIProfile or RayHFProfile (NmF2, hmF2, foF2, TEC)

    Priority order:
      1. PyRayHF  — storm conditions (Kp >= 5 or Dst <= -100)
                    Ray-traces virtual height using IRI Ne profile.
                    Note: SAMI3 physics model is not integrated.
      2. A-CHAIM  — high latitudes (|lat| >= 60)
      3. IRTAM    — real-time assimilated, nominal conditions
      4. IRI      — calm fallback
    """

    selection: SelectionResult = select_model(lat, kp, dst, irtam_available)
    logger.info(f"Model selected: {selection.model} | {selection.reason}")

    # D3 fix: profile initialised to None — each branch sets it explicitly.
    # If profile is still None at the return site, something is wrong.
    profile = None
    model_used = None

    if selection.model == "IRI":
        profile = get_iri_profile(lat, lon, dt)
        model_used = "IRI"

    elif selection.model == "IRTAM":
        irtam_profile = get_irtam_profile(lat, lon, dt)
        if is_irtam_available(irtam_profile):
            profile = irtam_profile
            model_used = "IRTAM"
        else:
            logger.warning("PyIRTAM returned no usable profile — falling back to IRI")
            profile = get_iri_profile(lat, lon, dt)
            model_used = "IRI"

    elif selection.model == "A-CHAIM":
        achaim_result = get_achaim_profile(lat, lon, ACHAIM_DB_PATH, ACHAIM_EXE_PATH)
        if achaim_result is not None:
            profile = IRIProfile(
                lat=lat,
                lon=lon,
                datetime=dt,
                NmF2=achaim_result.get("NmF2"),
                hmF2=achaim_result.get("hmF2"),
                foF2=None,
                TEC=None,
                source="A-CHAIM"
            )
            model_used = "A-CHAIM"
        else:
            logger.warning("A-CHAIM returned None — falling back to IRI")
            profile = get_iri_profile(lat, lon, dt)
            model_used = "IRI"

    elif selection.model == "PyRayHF":
        # Issue 3 fix: renamed from "SAMI3" — this slot uses PyRayHF ray tracing,
        # not the SAMI3 physics model. PyRayHF computes virtual height directly
        # from an IRI electron density profile via ray tracing.
        rayhf_profile = get_rayhf_profile(lat, lon, dt)
        if is_rayhf_available(rayhf_profile):
            profile = rayhf_profile
            model_used = "PyRayHF"
        else:
            logger.warning("PyRayHF returned no usable profile — falling back to IRI")
            profile = get_iri_profile(lat, lon, dt)
            model_used = "IRI"

    if profile is None or model_used is None:
        raise ValueError(
            f"No ionospheric profile produced for model='{selection.model}' "
            f"at lat={lat}, lon={lon}, dt={dt}. This is a bug."
        )

    return {
        "model_used": model_used,          # D1: actual model used (GP routes on this)
        "selected_model": selection.model, # D1: attempted model (audit trail)
        "reason": selection.reason,
        "profile": profile
    }