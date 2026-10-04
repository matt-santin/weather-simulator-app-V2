"""Seasonal normals at a place: a 30-year climate, day by day.

Read at the cells of the search (temperatures at 0.1 deg where there is a cell,
precipitation at 0.25 deg), from ERA5-Land and ERA5, whatever the period shown:
the normal of a simulated summer is the one of the observed climate.

Three reference periods, the 30-year normals the store holds whole (it starts
in 1970): 1971-2000, 1981-2010, 1991-2020, the last by default.

The normal of a day is the mean of every value of the reference period within
HALF_WINDOW days of that date, any year: 30 years x 15 days, about 450 values.
Days are keyed on a 366-day calendar, 29 February included; the window wraps
around the new year.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.app.api.contract import NormalDay, Normals
from src.app.store import Cell, Store

REFERENCES = (1971, 1981, 1991)  # first years
DEFAULT = 1991
YEARS = 30
HALF_WINDOW = 7  # days either side: a 15-day window
SOURCE = "era5"
NAMES = {"tasmax": "temperature_max", "tasmin": "temperature_min", "pr": "precipitation"}


def calendar_day(day: date) -> int:
    """Position of the month and day in a leap year, 0 to 365."""
    return (date(2000, day.month, day.day) - date(2000, 1, 1)).days


def reference(first: int) -> tuple[date, date]:
    return date(first, 1, 1), date(first + YEARS - 1, 12, 31)


def label(first: int) -> str:
    """"1991-2020", as the visitor reads it."""
    return f"{first}-{first + YEARS - 1}"


def climatology(store: Store, cell: Cell, first: int) -> dict[str, np.ndarray]:
    """Each variable's smoothed normal, indexed by calendar_day, NaN where no value."""
    start, end = reference(first)
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


def run(store: Store, cell: Cell, start: date, end: date, first: int = DEFAULT) -> Normals:
    normal = climatology(store, cell, first)
    reference_start, reference_end = reference(first)
    days = []
    for k in range((end - start).days + 1):
        day = start + timedelta(days=k)
        at = calendar_day(day)
        days.append(NormalDay(
            date=day,
            **{field: _round(normal[name][at]) for name, field in NAMES.items()},
        ))
    return Normals(
        reference_start=reference_start,
        reference_end=reference_end,
        window_days=2 * HALF_WINDOW + 1,
        days=days,
    )


def _round(value: float) -> float | None:
    # Two decimals, not one: the chart adds the daily rain up over 92 days.
    return None if np.isnan(value) else round(float(value), 2)
