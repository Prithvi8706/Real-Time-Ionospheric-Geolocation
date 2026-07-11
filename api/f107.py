"""
F10.7 solar-flux auto-lookup from NASA OMNI2 (TODOS item 4).

When a /locate caller omits f107, resolve_f107() fetches the yearly OMNI2
file for the request date, parses the daily F10.7 column, and caches every
day of that year in-process. Any failure (offline, air-gapped, bad data)
falls back to the 130.0 SFU training-time default — the service never
blocks on this lookup beyond one fetch attempt per year.

Column positions and fill-value handling match data/fetch_omni.py.
"""

import logging
import urllib.request
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

DEFAULT_F107 = 130.0
OMNI2_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_{year}.dat"
FETCH_TIMEOUT_S = 10

# F10.7 is a daily value: cache key = calendar date.
_cache: dict = {}
_failed_years: set = set()


def _fetch_year(year: int) -> str:
    """Download the raw OMNI2 hourly file for one year (network touchpoint)."""
    url = OMNI2_URL.format(year=year)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
        return resp.read().decode("ascii", errors="replace")


def _parse_year_into_cache(year: int, raw: str) -> None:
    """Store one F10.7 value per calendar day; skip OMNI fill values (>=999)."""
    jan1 = date(year, 1, 1)
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) < 51:
            continue
        try:
            row_year = int(parts[0])
            doy = int(parts[1])
            f107 = float(parts[50])
        except (ValueError, IndexError):
            continue
        if row_year != year or f107 >= 999.0 or not (50.0 <= f107 <= 300.0):
            continue
        day = jan1 + timedelta(days=doy - 1)
        if day not in _cache:
            _cache[day] = f107


def lookup_f107(day: date):
    """Daily F10.7 (SFU) for `day`, or None if unavailable."""
    if day in _cache:
        return _cache[day]
    if day.year in _failed_years:
        return None
    try:
        raw = _fetch_year(day.year)
    except Exception as e:
        logger.warning("OMNI2 F10.7 fetch failed for %d (%s: %s) — "
                       "using default until restart", day.year, type(e).__name__, e)
        _failed_years.add(day.year)
        return None
    _parse_year_into_cache(day.year, raw)
    if day not in _cache:
        # fetched fine but this date has no usable value — don't refetch
        _cache[day] = None
    return _cache[day]


def resolve_f107(explicit, dt: datetime):
    """
    Resolve the F10.7 to use for a request.

    Returns (value, source): source is "caller" when supplied explicitly,
    "omniweb" when looked up by date, "default" otherwise.
    """
    if explicit is not None:
        return explicit, "caller"
    value = lookup_f107(dt.date())
    if value is not None:
        return value, "omniweb"
    return DEFAULT_F107, "default"
