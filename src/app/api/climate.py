"""The climate diagram at a place: twelve monthly means over 15 years.

The window is centred on the year of the search (the year of its middle day),
and never mixes two sources: it is shifted to stay inside the served period
that holds that year (ERA5 1970-2025, corrected CORDEX 2027-2100). 2020 gives
2011-2025, 2030 gives 2027-2041, 2098 gives 2086-2100.

Beside it, the same twelve months over a reference period of the normals
(normals.REFERENCES), always ERA5.

Per month: mean temperature (tas), mean minimum and maximum, and the rain of
an average month (mean daily rain x mean length of that month). A month is dry
when P <= 2T, P in mm and T in deg C (Bagnouls and Gaussen, 1957).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.app.api import normals
from src.app.api.contract import Climate, ClimateMonth, ClimateWindow
from src.app.store import PERIODS, Cell, Period, Store

SPAN = 15
NAMES = {
    "tas": "temperature_mean",
    "tasmin": "temperature_min",
    "tasmax": "temperature_max",
    "pr": "precipitation",
}
SOURCES = {"era5": "ERA5", "cordex": "CORDEX EUR-11 corrigé"}


def window(year: int) -> tuple[Period, int, int] | None:
    """The served period holding ``year``, and the SPAN years drawn from it."""
    period = next((p for p in PERIODS if p.start.year <= year <= p.end.year), None)
    if period is None:
        return None
    first = year - SPAN // 2
    first = max(period.start.year, min(first, period.end.year - SPAN + 1))
    return period, first, first + SPAN - 1


def months(store: Store, source: str, cell: Cell, first: int, last: int) -> list[ClimateMonth]:
    start, end = date(first, 1, 1), date(last, 12, 31)
    values = store.series(source, cell, start, end, tuple(NAMES))
    n = (end - start).days + 1
    month = np.array([(start + timedelta(days=k)).month for k in range(n)])
    years = last - first + 1
    out = []
    for m in range(1, 13):
        at = month == m
        mean = {name: _mean(np.array(values[name], dtype=float)[at]) for name in NAMES}
        length = at.sum() / years
        rain = None if mean["pr"] is None else mean["pr"] * length
        t = mean["tas"]
        out.append(ClimateMonth(
            month=m,
            temperature_mean=_round(t),
            temperature_min=_round(mean["tasmin"]),
            temperature_max=_round(mean["tasmax"]),
            precipitation=_round(rain),
            dry=None if rain is None or t is None else bool(rain <= 2 * t),
        ))
    return out


def run(store: Store, cell: Cell, year: int, reference: int) -> Climate:
    period, first, last = window(year)
    ref_start, ref_end = normals.reference(reference)
    return Climate(
        window=ClimateWindow(
            start_year=first,
            end_year=last,
            origin="simulated" if period.source == "cordex" else "observed",
            source=SOURCES[period.source],
        ),
        months=months(store, period.source, cell, first, last),
        reference=ClimateWindow(
            start_year=ref_start.year,
            end_year=ref_end.year,
            origin="observed",
            source=SOURCES[normals.SOURCE],
        ),
        reference_months=months(store, normals.SOURCE, cell, ref_start.year, ref_end.year),
    )


def _mean(values: np.ndarray) -> float | None:
    ok = values[~np.isnan(values)]
    return float(ok.mean()) if ok.size else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)
