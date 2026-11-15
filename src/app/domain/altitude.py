"""Temperatures brought from the altitude of their cell to that of the place.

A 0.1 deg cell is a mean over about 80 km2: in the mountains it can stand
hundreds of metres above a valley town, or below a summit. Against 1 617 ECA&D
stations over 1991-2020 (figures/altitude/temperatures.py), the temperatures of
the cell are off by the altitude gap: where the cell is 300 m or more above the
station, the summer maximum is 4.0 K too cold on average.

The correction is a lapse rate per calendar month, one for the daily minimum
and one for the maximum, fitted on half of the stations (the slope of the gap
between cell and station against their altitude gap) and checked on the other
half: the mean absolute gap falls to 0.5-0.6 K in summer and 0.6-1.1 K in winter
where the altitudes differ by 300 m or more. A single 6.5 K/km does worse than
nothing on winter minima, which inversions flatten. The daily mean takes the
mean of the two rates.

It moves the mean, not the shape: a day of inversion stays badly rendered.
Fitted on cells whose temperatures come from E-OBS; on the fallback cells
(ERA5-Land) the few stations there do not support it, and it is not applied.
"""

from __future__ import annotations

from datetime import date

import numpy as np

# K per km, January to December.
LAPSE_K_PER_KM = {
    "tasmin": (2.4, 3.3, 4.1, 4.2, 4.2, 4.2, 4.0, 3.6, 3.6, 3.1, 3.0, 2.4),
    "tasmax": (3.9, 5.7, 7.5, 8.4, 8.4, 8.0, 7.8, 7.6, 7.2, 6.1, 4.7, 3.5),
}
LAPSE_K_PER_KM["tas"] = tuple(
    round((low + high) / 2, 2) for low, high in zip(LAPSE_K_PER_KM["tasmin"], LAPSE_K_PER_KM["tasmax"]))

# Altitudes a place may be given: a wider gap than this to the cell is not
# believed (2 500 m is the largest among the stations of the fit) and is cut.
MIN_ELEVATION_M = -500.0
MAX_ELEVATION_M = 6000.0
MAX_LIFT_M = 2500.0


def lift(cell_m: float, place_m: float) -> float:
    """How far the cell stands above the place, in metres, cut at MAX_LIFT_M."""
    return float(np.clip(cell_m - place_m, -MAX_LIFT_M, MAX_LIFT_M))


def shift(name: str, start: date, n: int, lift_m: float) -> np.ndarray:
    """What to add to ``n`` daily values of ``name`` from ``start``, in degrees:
    a cell above its place is colder than it, and is warmed."""
    days = np.datetime64(start.isoformat()) + np.arange(n)
    month = days.astype("datetime64[M]").astype(int) % 12
    return np.asarray(LAPSE_K_PER_KM[name])[month] * lift_m / 1000.0
