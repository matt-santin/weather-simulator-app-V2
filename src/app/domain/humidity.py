"""Wet-bulb temperature, and the humid-heat level the card turns on.

**Stull (2011), with Open-Meteo's ``min(twet, t)`` guard**, as in V1. Against
exact psychrometry: -1.0 to +0.65 degC, mean absolute error under 0.3 degC,
plus a missing pressure term reaching 0.9 degC at 1500 m in hot dry air.

**Fed the daily mean relative humidity and the daily mean temperature.** V1
fed a dew point, which tracks the moisture better over a day (0.04 to 0.08
degC RMSE against an hourly-resolved mean, 0.07 to 0.42 through relative
humidity). CORDEX serves no dew point, only ``hurs``, and ERA5 serves ``hurs``
too (daily mean of the hourly values): the same input on both sides matters
more than the better one on one side.

**The daily mean, never the maximum**: the maximum reconstructs from daily
aggregates ten times worse, and heat harms by dose rather than by peak.

The reading is one-sided: a high value is certain danger, a moderate one does
not exclude a difficult few hours. The level is a floor on severity, never a
certificate of safety.
"""

from __future__ import annotations

import math

from src.app.domain import thresholds
from src.app.domain.records import DailyRecord


def wet_bulb(temperature_mean: float | None, relative_humidity: float | None) -> float | None:
    """The day's mean wet-bulb temperature in degrees Celsius, or ``None``.

    ``None`` when either input is missing: a gap is a gap.

    Relative humidity is capped at 100 (the fit's domain). The trailing ``min``
    clamps the fit, which can exceed the air temperature at saturation.
    """
    if temperature_mean is None or relative_humidity is None:
        return None

    t = temperature_mean
    rh = min(100.0, relative_humidity)
    value = (
        t * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t + rh)
        - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh)
        - 4.686035
    )
    return min(value, t)


def humid_heat(wet_bulb_mean: float | None) -> int | None:
    """The level a day carries: 0, 1, 2 — or ``None`` when there is no reading.

    Zero and null say different things and the interface needs both. Zero is an
    answer: this day was measured and there is nothing to report. Null is the
    absence of one, and a card must no more invent a level than it invents a
    sky class.

    Two levels and not five. A wet bulb means nothing to a reader as a number —
    31 °C is lethal and reads as mild — so the card shows a word, and a word
    scale finer than "marked" and "beyond what a body compensates" would claim
    a gradation the daily mean cannot support.
    """
    if wet_bulb_mean is None:
        return None
    if wet_bulb_mean >= thresholds.HUMID_HEAT_EXTREME_C:
        return 2
    if wet_bulb_mean >= thresholds.HUMID_HEAT_C:
        return 1
    return 0


def wet_bulb_of_record(record: DailyRecord) -> float | None:
    """The same rule, applied to a day of the assembled series."""
    return wet_bulb(record.temperature_mean, record.relative_humidity_mean)
