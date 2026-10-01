"""The daily record: the single vocabulary shared by every layer.

One record is one day, whatever its source. ERA5 and corrected CORDEX serve
the same seven variables, on the same grid and in the same units, so the two
sources differ by ``origin`` alone: never by which fields carry a value, never
by how a value is computed.

Units, as the store serves them, except the wind:

- temperatures      degrees Celsius
- precipitation     millimetres per day
- cloud cover       percent
- relative humidity percent
- wind speed        kilometres per hour (stored in m/s)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Origin(StrEnum):
    """Where a day comes from: what happened (ERA5), or what is modelled (CORDEX).

    The interface warns on simulated days, and on those only.
    """

    OBSERVED = "observed"
    SIMULATED = "simulated"


@dataclass(frozen=True, slots=True)
class DailyRecord:
    """One day. Every measured field is optional: a gap stays a gap."""

    date: date
    origin: Origin
    source: str | None = None
    temperature_min: float | None = None
    temperature_max: float | None = None
    # For the snow criterion and the wet bulb only; not displayed.
    temperature_mean: float | None = None
    # For the wet bulb only; not displayed.
    relative_humidity_mean: float | None = None
    precipitation: float | None = None
    cloud_cover: float | None = None
    wind_speed_mean: float | None = None
