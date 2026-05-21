from datetime import datetime
from models.hybrid_selector import select_model, SelectionResult
from models.iri.iri_wrapper import get_iri_profile, IRIProfile
from models.achaim.achaim_wrapper import get_achaim_profile
import logging

logger = logging.getLogger(__name__)

# ── A-CHAIM config ───────────────────────────────────────────────────────────
ACHAIM_EXE_PATH = "C:/Users/prith/Downloads/A-CHAIM_User_Release-6.0.3/A-CHAIM_User_Release-6.0.3/C/ACHAIM/ACHAIM.exe"
ACHAIM_DB_PATH  = "C:/Users/prith/Downloads/A-CHAIM_User_Release-6.0.3/A-CHAIM_User_Release-6.0.3/C/example/example.db"


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
      - model_used: which model was selected
      - reason: why that model was chosen
      - profile: IRIProfile (NmF2, hmF2, foF2, TEC)
    """

    selection: SelectionResult = select_model(lat, kp, dst, irtam_available)
    logger.info(f"Model selected: {selection.model} | {selection.reason}")

    # Default to IRI so profile is always bound
    profile = get_iri_profile(lat, lon, dt)

    if selection.model == "IRI":
        profile = get_iri_profile(lat, lon, dt)

    elif selection.model == "IRTAM":
        logger.warning("IRTAM selected but not yet implemented — falling back to IRI")
        profile = get_iri_profile(lat, lon, dt)

    elif selection.model == "A-CHAIM":
        achaim_result = get_achaim_profile(lat, lon, ACHAIM_DB_PATH, ACHAIM_EXE_PATH)
        if achaim_result is not None:
            # Build IRIProfile with all required fields
            profile = IRIProfile(
                lat=lat,
                lon=lon,
                datetime=dt,
                NmF2=achaim_result.get("NmF2"),
                hmF2=achaim_result.get("hmF2"),
                foF2=None,   # A-CHAIM doesn't output foF2 directly
                TEC=None,    # not requested (alt=0 mode)
                source="A-CHAIM"
            )
        else:
            logger.warning("A-CHAIM returned None — falling back to IRI")
            profile = get_iri_profile(lat, lon, dt)

    elif selection.model == "SAMI3":
        logger.warning("SAMI3 selected but not yet implemented — falling back to IRI")
        profile = get_iri_profile(lat, lon, dt)

    return {
        "model_used": selection.model,
        "reason": selection.reason,
        "profile": profile
    }