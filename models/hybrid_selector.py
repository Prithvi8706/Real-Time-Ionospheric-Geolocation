from dataclasses import dataclass
from typing import Literal
import logging

logger = logging.getLogger(__name__)

ModelChoice = Literal["IRTAM", "IRI", "A-CHAIM", "PyRayHF"]

@dataclass
class SelectionResult:
    model: ModelChoice
    reason: str

def select_model(
    lat: float,
    kp: float,
    dst: float,
    irtam_available: bool = False
) -> SelectionResult:
    """
    Decide which ionospheric model to use based on conditions.

    Priority order:
      1. PyRayHF — storm conditions (Kp >= 5 or Dst <= -100)
                   Ray-tracing virtual height via PyRayHF (IRI Ne profile).
                   Note: SAMI3 physics model is not integrated; PyRayHF is
                   the storm-time proxy implemented in this slot.
      2. A-CHAIM — high latitudes (|lat| >= 60)
      3. IRTAM   — real-time assimilated, if available
      4. IRI     — calm fallback
    """

    if kp >= 5.0 or dst <= -100.0:
        return SelectionResult(
            model="PyRayHF",
            reason=f"Storm conditions: Kp={kp}, Dst={dst} — PyRayHF ray-tracing virtual height"
        )

    if abs(lat) >= 60.0:
        return SelectionResult(
            model="A-CHAIM",
            reason=f"High latitude: lat={lat}°"
        )

    if irtam_available:
        return SelectionResult(
            model="IRTAM",
            reason="IRTAM available and conditions are nominal"
        )

    return SelectionResult(
        model="IRI",
        reason=f"Calm conditions (Kp={kp}, Dst={dst}), IRTAM unavailable"
    )