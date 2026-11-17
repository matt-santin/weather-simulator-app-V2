"""Seasonal normals at a place: a 30-year climate, day by day.

Read at the cells of the search (temperatures at 0.1 deg where there is a cell,
precipitation at 0.25 deg), from the era5land and era5 groups (temperatures from
E-OBS where the store says so, src.store.build), whatever the period shown:
the normal of a simulated summer is the one of the observed climate.

Three reference periods, the 30-year normals the store holds whole (it starts
in 1970): 1971-2000, 1981-2010, 1991-2020, the last by default.

The normal of a day is the mean of every value of the reference period within
HALF_WINDOW days of that date, any year: 30 years x 15 days, about 450 values.
Days are keyed on a 366-day calendar, 29 February included; the window wraps
around the new year.

The water left in the soil has its normal too, by the same mean: the balance
of the place over the past (src.app.api.soil, ERA5 from 1970, full on its first
day), read over the reference years. With it, its extremes: the lowest and
the highest value of the same 30 years x 15 days, as Meteo-France draws the
range of its soil moisture index around the 1991-2020 normal. None where the
store has no solar radiation.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.app.api import soil
from src.app.api.contract import NormalDay, Normals
from src.app.store import PERIODS, Cell, Store

REFERENCES = (1971, 1981, 1991)  # first years
DEFAULT = 1991
YEARS = 30
HALF_WINDOW = 7  # days either side: a 15-day window
SOURCE = "era5"
NAMES = {"tasmax": "temperature_max", "tasmin": "temperature_min", "pr": "precipitation"}
SOIL = "soil_water"
SOIL_LOW, SOIL_HIGH = "soil_water_min", "soil_water_max"


def calendar_day(day: date) -> int:
    """Position of the month and day in a leap year, 0 to 365."""
    return (date(2000, day.month, day.day) - date(2000, 1, 1)).days


def reference(first: int) -> tuple[date, date]:
    return date(first, 1, 1), date(first + YEARS - 1, 12, 31)


def label(first: int) -> str:
    """"1991-2020", as the visitor reads it."""
    return f"{first}-{first + YEARS - 1}"


def soil_water(store: Store, cell: Cell, start: date, end: date) -> np.ndarray | None:
    """Percent of the available water left each day of start..end, past days only."""
    period = next(p for p in PERIODS if p.source == SOURCE)
    found = soil.balance(store, period, cell)
    if found is None:
        return None
    origin, whole = found
    return 100 * whole.fill[(start - origin).days:(end - origin).days + 1]


def climatology(store: Store, cell: Cell, first: int) -> dict[str, np.ndarray]:
    """Each variable's smoothed normal, indexed by calendar_day, NaN where no value."""
    start, end = reference(first)
    values = store.values(SOURCE, cell, start, end, tuple(NAMES))
    water = soil_water(store, cell, start, end)
    if water is not None:
        values[SOIL] = water
    n = (end - start).days + 1
    keys = np.array([calendar_day(start + timedelta(days=k)) for k in range(n)])
    out = {}
    for name, data in values.items():
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
        if name == SOIL:
            low, high = np.full(366, np.inf), np.full(366, -np.inf)
            np.minimum.at(low, keys[ok], data[ok])
            np.maximum.at(high, keys[ok], data[ok])
            low = np.min([np.roll(low, k) for k in window], axis=0)
            high = np.max([np.roll(high, k) for k in window], axis=0)
            out[SOIL_LOW] = np.where(np.isfinite(low), low, np.nan)
            out[SOIL_HIGH] = np.where(np.isfinite(high), high, np.nan)
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
            **{name: _round(normal[name][at], 1) if name in normal else None
               for name in (SOIL, SOIL_LOW, SOIL_HIGH)},
        ))
    return Normals(
        reference_start=reference_start,
        reference_end=reference_end,
        window_days=2 * HALF_WINDOW + 1,
        days=days,
    )


def _round(value: float, digits: int = 2) -> float | None:
    # Two decimals, not one: the chart adds the daily rain up over 92 days.
    return None if np.isnan(value) else round(float(value), digits)
