from dataclasses import dataclass
from typing import Literal
import logging

logger = logging.getLogger(__name__)

ModelChoice = Literal["IRTAM", "IRI", "E-CHAIM", "SAMI3"]

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
      1. SAMI3   — storm conditions (Kp >= 5 or Dst <= -100)
      2. E-CHAIM — high latitudes (|lat| >= 60)
      3. IRTAM   — real-time, if server is up
      4. IRI     — calm fallback
    """

    if kp >= 5.0 or dst <= -100.0:
        return SelectionResult(
            model="SAMI3",
            reason=f"Storm conditions: Kp={kp}, Dst={dst}"
        )

    if abs(lat) >= 60.0:
        return SelectionResult(
            model="E-CHAIM",
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
