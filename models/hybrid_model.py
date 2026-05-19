from dataclasses import dataclass
from datetime import datetime
from models.hybrid_selector import select_model, SelectionResult
from models.iri.iri_wrapper import get_iri_profile, IRIProfile
import logging

logger = logging.getLogger(__name__)

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

    if selection.model == "IRI":
        profile = get_iri_profile(lat, lon, dt)

    elif selection.model == "IRTAM":
        # Placeholder — swap in PyIRTAM once LGDC responds
        logger.warning("IRTAM selected but not yet implemented — falling back to IRI")
        profile = get_iri_profile(lat, lon, dt)

    elif selection.model == "E-CHAIM":
        # Placeholder — E-CHAIM wrapper pending
        logger.warning("E-CHAIM selected but not yet implemented — falling back to IRI")
        profile = get_iri_profile(lat, lon, dt)

    elif selection.model == "SAMI3":
        # Placeholder — SAMI3 wrapper pending
        logger.warning("SAMI3 selected but not yet implemented — falling back to IRI")
        profile = get_iri_profile(lat, lon, dt)

    return {
        "model_used": selection.model,
        "reason": selection.reason,
        "profile": profile
    }
