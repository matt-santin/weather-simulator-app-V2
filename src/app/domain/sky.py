"""The sky class: one day of numbers turned into one of five words.

One function, applied to ERA5 and CORDEX days alike: the rule must not differ
between the past and the future. It reads daily aggregates only, since CORDEX
serves nothing finer.

Thresholds (src.app.domain.thresholds) come from V1, measured on Open-Meteo
data: on the days each class captures, the light reaching the ground is about
90 %, 80 % and 60 % of a clear sky. A daily mean hides the shape of the day, so
the pictogram describes the kind of day, not that day.
"""

from __future__ import annotations

from enum import StrEnum

from src.app.domain import thresholds
from src.app.domain.records import DailyRecord


class SkyClass(StrEnum):
    """The five classes. Carried through the JSON contract; the pictogram is not.

    Section 4 keeps the emoji on the display side alone, so that moving to a
    drawn icon set later touches nothing but the rendering.
    """

    CLEAR = "clear"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"
    RAIN = "rain"
    SNOW = "snow"


def classify(
    precipitation: float | None,
    temperature_mean: float | None,
    cloud_cover: float | None,
) -> SkyClass | None:
    """The class of one day, or ``None`` when the day cannot be classified.

    ``None`` is returned rather than a guess. A missing value is a gap in the
    data, and substituting a class for it would be a data-treatment decision
    made in passing.

    The wet gate is crossed first, and rules 1 and 2 share it, so they partition
    the same set of days rather than overlap: among wet days, the temperature
    decides the phase. Snow *depth* deliberately plays no part, though it was
    the original basis. The climate model serves it in patches that are neither
    seasonal nor regular — none of the five eligible models serves it at the
    tropical sites, and half a year is missing at Christchurch — while the
    reanalyses serve it faithfully. Reading it on one side only would move the
    seam instead of removing it.
    """
    if precipitation is None:
        return None

    if precipitation >= thresholds.PRECIPITATION_MM:
        if temperature_mean is None:
            return None
        if temperature_mean < thresholds.SNOW_TEMPERATURE_C:
            return SkyClass.SNOW
        return SkyClass.RAIN

    if cloud_cover is None:
        return None
    if cloud_cover >= thresholds.OVERCAST_PERCENT:
        return SkyClass.OVERCAST
    if cloud_cover >= thresholds.CLOUDY_PERCENT:
        return SkyClass.CLOUDY
    return SkyClass.CLEAR


def classify_record(record: DailyRecord) -> SkyClass | None:
    """The same rule, applied to a day of the assembled series."""
    return classify(record.precipitation, record.temperature_mean, record.cloud_cover)
