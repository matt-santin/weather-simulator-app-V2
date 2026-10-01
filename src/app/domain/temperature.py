"""The temperature band: one degree reading turned into one of nine steps.

One function for the maximum and the minimum, on one shared scale, so that
12 degC is the same colour on both. The band is a rule and travels in the
contract; the colours stay in the stylesheet.
"""

from __future__ import annotations

from src.app.domain import thresholds
from src.app.domain.records import DailyRecord

# The number of bands the edges cut the line into: one below the first edge, one
# above the last, and one between each pair.
BAND_COUNT = len(thresholds.TEMPERATURE_BAND_EDGES) + 1


def band(temperature: float | None) -> int | None:
    """Which of the nine bands a temperature falls in, or ``None`` for a gap.

    Band 0 is everything below the first edge and band 8 everything at or above
    the last. A value sitting exactly on an edge falls in the warmer of the two
    bands, the same convention the cloud thresholds use.

    ``None`` rather than a guess, as everywhere else here: a missing temperature
    is a hole in the data, and giving it a colour would be inventing one.
    """
    if temperature is None:
        return None
    for index, edge in enumerate(thresholds.TEMPERATURE_BAND_EDGES):
        if temperature < edge:
            return index
    return len(thresholds.TEMPERATURE_BAND_EDGES)


def bands_of(record: DailyRecord) -> tuple[int | None, int | None]:
    """The two bands of one day of the assembled series, minimum first."""
    return band(record.temperature_min), band(record.temperature_max)
