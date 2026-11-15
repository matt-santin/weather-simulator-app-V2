"""Snow on the ground, from daily mean temperature and precipitation.

A degree-day stock of water (thresholds.SNOW_*): what falls on a cold day is
kept, each degree above zero melts some of it, and the stock starts empty every
1 August. There is snow on the ground on a day whose stock, after the day's
fall and melt, holds SNOW_STOCK_MM or more.

The same computation for past and simulated days. It knows nothing of the
place: the altitude gate and the ratio method that turns a simulated count into
a displayed one are the caller's (src.app.api.climate).
"""

from __future__ import annotations

from datetime import date

import numpy as np

from src.app.domain import thresholds


def on_ground(tas: np.ndarray, pr: np.ndarray, start: date) -> np.ndarray:
    """True on the days with snow on the ground. ``tas`` in deg C and ``pr`` in
    mm, one value per day from ``start``. A day without temperature leaves the
    stock as it was; a day without precipitation adds nothing."""
    month, first = _calendar(start, len(tas))
    reset = (first & (month == thresholds.SNOW_RESET_MONTH)).tolist()
    stock = 0.0
    out = []
    for t, p, empty in zip(np.asarray(tas, float).tolist(), np.asarray(pr, float).tolist(), reset):
        if empty:
            stock = 0.0
        if t == t:  # not NaN
            fall = p if p == p and t < thresholds.SNOW_FALL_C else 0.0
            melt = thresholds.SNOW_MELT_MM_PER_DEGREE_DAY * max(t, 0.0)
            stock = max(stock + fall - melt, 0.0)
        out.append(stock >= thresholds.SNOW_STOCK_MM)
    return np.array(out, dtype=bool)


def per_winter(tas: np.ndarray, pr: np.ndarray, start: date) -> dict[int, int]:
    """Days with snow on the ground in each winter of the series, November to
    April, a winter being named by the year it ends in. The series should start
    on a 1 August and end after an April: a winter cut short is counted short."""
    month, _ = _calendar(start, len(tas))
    days = np.datetime64(start.isoformat()) + np.arange(len(tas))
    year = days.astype("datetime64[Y]").astype(int) + 1970
    winter = year + (month >= thresholds.SNOW_RESET_MONTH)
    season = np.isin(month, thresholds.SNOW_SEASON_MONTHS)
    snow = on_ground(tas, pr, start)
    return {int(w): int(snow[season & (winter == w)].sum()) for w in np.unique(winter[season])}


def _calendar(start: date, n: int) -> tuple[np.ndarray, np.ndarray]:
    """The month of each day, and whether it is the first of its month."""
    days = np.datetime64(start.isoformat()) + np.arange(n)
    months = days.astype("datetime64[M]")
    return months.astype(int) % 12 + 1, days == months.astype("datetime64[D]")
