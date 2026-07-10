"""
Test signal generator — DRDO DIA-CoE/EW/02 deliverable.

Places emitters at KNOWN lat/lon and synthesizes the exact
(azimuth, elevation, frequency) a receiver would observe via forward
geometry through the real hybrid ionosphere. Output signals are
ground truth the SSL solver's accuracy can be measured against.

Design: docs/superpowers/specs/2026-07-01-test-signal-generator-and-bearing-noise-study-design.md

Run from repo root:
    python data/generate_test_signals.py
Writes:
    data/processed/test_signals.csv
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from models.hybrid_model import get_ionosphere
from models.ssl_algorithm import (
    EARTH_RADIUS_KM,
    _extract_height,
    compute_transmitter_location,
)

# AH223 Ahmedabad receiver (spec §3.1)
RECEIVER_LAT = 23.0
RECEIVER_LON = 72.6

# Solver's validated elevation band — signals outside are invalid inputs
ELEVATION_MIN_DEG = 1.0
ELEVATION_MAX_DEG = 60.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle ground range on the same sphere the solver uses."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = phi2 - phi1
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlmb / 2) ** 2
    return float(2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a)))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing point1 -> point2, normalized to [0, 360)."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dlmb = np.radians(lon2 - lon1)
    y = np.sin(dlmb) * np.cos(phi2)
    x = np.cos(phi1) * np.sin(phi2) - np.sin(phi1) * np.cos(phi2) * np.cos(dlmb)
    return float(np.degrees(np.arctan2(y, x)) % 360.0)


def gc_midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Great-circle midpoint — the skywave bounce point for a single hop."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    lmb1 = np.radians(lon1)
    dlmb = np.radians(lon2 - lon1)
    bx = np.cos(phi2) * np.cos(dlmb)
    by = np.cos(phi2) * np.sin(dlmb)
    mid_lat = np.arctan2(
        np.sin(phi1) + np.sin(phi2),
        np.sqrt((np.cos(phi1) + bx) ** 2 + by ** 2),
    )
    mid_lon = lmb1 + np.arctan2(by, np.cos(phi1) + bx)
    return float(np.degrees(mid_lat)), float(np.degrees(mid_lon))
