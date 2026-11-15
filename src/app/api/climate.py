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

With them, the days with snow on the ground per winter (src.app.domain.snow),
over the winters that end in each window. A past window is counted on the past
data. A simulated one is not counted on the model alone, which has more cold
and wet days than the past data on the same years (docs/neige.md, section 5):
it is the past count of SNOW_BASELINE times the model's own change since those
years (ratio method). The baseline is fixed, whatever the reference drawn in
grey, so that a simulated figure does not move with the menu. No snow above
thresholds.SNOW_MAX_ELEVATION_M, where the cell's temperature is not the
place's, unless the temperatures were brought to the altitude of the place
(Cell.lift, src.app.domain.altitude).
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from src.app.api import normals
from src.app.api.contract import Climate, ClimateMonth, ClimateSnow, ClimateWindow, rounded
from src.app.domain import snow, thresholds
from src.app.store import FINE, PERIODS, Cell, Period, Store

SPAN = 15
SNOW_BASELINE = (1991, 2020)
NAMES = {
    "tas": "temperature_mean",
    "tasmin": "temperature_min",
    "tasmax": "temperature_max",
    "pr": "precipitation",
}


def source(store: Store, name: str, cell: Cell) -> str:
    return store.simulation.source if name == "cordex" else store.datasets(name, cell)


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
    values = store.values(source, cell, start, end, tuple(NAMES))
    n = (end - start).days + 1
    month = np.array([(start + timedelta(days=k)).month for k in range(n)])
    years = last - first + 1
    out = []
    for m in range(1, 13):
        at = month == m
        mean = {name: _mean(values[name][at]) for name in NAMES}
        length = at.sum() / years
        rain = None if mean["pr"] is None else mean["pr"] * length
        t = mean["tas"]
        out.append(ClimateMonth(
            month=m,
            temperature_mean=rounded(t),
            temperature_min=rounded(mean["tasmin"]),
            temperature_max=rounded(mean["tasmax"]),
            precipitation=rounded(rain),
            dry=None if rain is None or t is None else bool(rain <= 2 * t),
        ))
    return out


def snow_days(store: Store, source: str, cell: Cell, first: int, last: int) -> tuple[float, int]:
    """Mean days with snow on the ground per winter, and how many winters: those
    ending in first..last whose 1 August the source holds (1970 has none)."""
    held = max(store.first[name] for name in (source, FINE[source]) if name in store.first)
    while date(first - 1, thresholds.SNOW_RESET_MONTH, 1) < held:
        first += 1
    start, end = date(first - 1, thresholds.SNOW_RESET_MONTH, 1), date(last, 7, 31)
    values = store.values(source, cell, start, end, ("tas", "pr"))
    counts = snow.per_winter(values["tas"], values["pr"], start)
    return sum(counts.values()) / len(counts), len(counts)


def snows(store: Store, cell: Cell, period: Period, first: int, last: int,
          ref_first: int, ref_last: int) -> tuple[ClimateSnow | None, ClimateSnow | None]:
    """Snow on the ground over the window and over the reference, or nothing
    where it is not counted."""
    # The gate is for temperatures left at the altitude of their cell.
    altitude = store.elevation(cell)
    if cell.lift is None and (altitude is None or altitude > thresholds.SNOW_MAX_ELEVATION_M):
        return None, None
    days, winters = snow_days(store, normals.SOURCE, cell, ref_first, ref_last)
    reference = ClimateSnow(days=rounded(days), winters=winters)
    days, winters = snow_days(store, period.source, cell, first, last)
    if period.source != "cordex":
        return ClimateSnow(days=rounded(days), winters=winters), reference
    base = dict(baseline_start_year=SNOW_BASELINE[0], baseline_end_year=SNOW_BASELINE[1])
    model, _ = snow_days(store, "cordex", cell, *SNOW_BASELINE)
    if model < thresholds.SNOW_RARE_DAYS:
        return ClimateSnow(rare=True, winters=winters, **base), reference
    past, _ = snow_days(store, normals.SOURCE, cell, *SNOW_BASELINE)
    return ClimateSnow(days=rounded(past * days / model), winters=winters, **base), reference


def run(store: Store, cell: Cell, year: int, reference: int) -> Climate:
    period, first, last = window(year)
    ref_start, ref_end = normals.reference(reference)
    own, ref = snows(store, cell, period, first, last, ref_start.year, ref_end.year)
    return Climate(
        snow=own,
        reference_snow=ref,
        window=ClimateWindow(
            start_year=first,
            end_year=last,
            origin="simulated" if period.source == "cordex" else "observed",
            source=source(store, period.source, cell),
        ),
        months=months(store, period.source, cell, first, last),
        reference=ClimateWindow(
            start_year=ref_start.year,
            end_year=ref_end.year,
            origin="observed",
            source=source(store, normals.SOURCE, cell),
        ),
        reference_months=months(store, normals.SOURCE, cell, ref_start.year, ref_end.year),
    )


def _mean(values: np.ndarray) -> float | None:
    ok = values[~np.isnan(values)]
    return float(ok.mean()) if ok.size else None
