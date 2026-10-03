"""Seasonal normals at a place: the 1991-2020 climate, day by day.

Temperatures only, read at the cells of the search (0.1 deg where there is a
cell, 0.25 deg otherwise), from ERA5-Land or ERA5, whatever the period shown:
the normal of a simulated summer is the one of the observed climate.

The normal of a day is the mean of every value from REFERENCE within
HALF_WINDOW days of that date, any year: 30 years x 15 days, about 450 values.
Days are keyed on a 366-day calendar, 29 February included; the window wraps
around the new year.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.app.api.contract import NormalDay, Normals
from src.app.store import Cell, Store

REFERENCE = (date(1991, 1, 1), date(2020, 12, 31))
HALF_WINDOW = 7  # days either side: a 15-day window
SOURCE = "era5"
NAMES = {"tasmax": "temperature_max", "tasmin": "temperature_min"}


def calendar_day(day: date) -> int:
    """Position of the month and day in a leap year, 0 to 365."""
    return (date(2000, day.month, day.day) - date(2000, 1, 1)).days


def climatology(store: Store, cell: Cell) -> dict[str, np.ndarray]:
    """Each variable's smoothed normal, indexed by calendar_day, NaN where no value."""
    start, end = REFERENCE
    values = store.series(SOURCE, cell, start, end, tuple(NAMES))
    n = (end - start).days + 1
    keys = np.array([calendar_day(start + timedelta(days=k)) for k in range(n)])
    out = {}
    for name, series in values.items():
        data = np.array(series, dtype=float)
        ok = ~np.isnan(data)
        sums = np.bincount(keys[ok], weights=data[ok], minlength=366)
        counts = np.bincount(keys[ok], minlength=366).astype(float)
        # Pooling sums and counts, rather than smoothing daily means, gives each
        # value the same weight: 29 February holds 8 years, the others 30.
        window = range(-HALF_WINDOW, HALF_WINDOW + 1)
        total = sum(np.roll(sums, k) for k in window)
        count = sum(np.roll(counts, k) for k in window)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[name] = total / count
    return out


def run(store: Store, cell: Cell, start: date, end: date) -> Normals:
    normal = climatology(store, cell)
    days = []
    for k in range((end - start).days + 1):
        day = start + timedelta(days=k)
        at = calendar_day(day)
        days.append(NormalDay(
            date=day,
            **{field: _round(normal[name][at]) for name, field in NAMES.items()},
        ))
    return Normals(
        reference_start=REFERENCE[0],
        reference_end=REFERENCE[1],
        window_days=2 * HALF_WINDOW + 1,
        days=days,
    )


def _round(value: float) -> float | None:
    return None if np.isnan(value) else round(float(value), 1)
