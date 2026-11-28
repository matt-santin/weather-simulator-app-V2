"""The climate diagram at a place: twelve monthly means over 15 years.

The window is centred on the year of the search (the year of its middle day),
and never mixes two sources: it is shifted to stay inside the served period
that holds that year (ERA5 1970-2025, corrected CORDEX 2027-2100). 2020 gives
2011-2025, 2030 gives 2027-2041, 2098 gives 2086-2100.

With each set of twelve months, its Köppen-Geiger class (src.app.domain.koppen),
computed on the very means drawn: 15 years for the window, 30 for the reference.

Beside it, the same twelve months over a reference period of the normals
(normals.REFERENCES), always the past data (temperatures E-OBS, rain ERA5).

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
from src.app.domain import koppen, snow, thresholds
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


def counted(store: Store, cell: Cell) -> bool:
    """Whether snow is counted at the cell. The gate is for temperatures left at
    the altitude of their cell."""
    altitude = store.elevation(cell)
    return cell.lift is not None or (
        altitude is not None and altitude <= thresholds.SNOW_MAX_ELEVATION_M)


def rare(store: Store, cell: Cell) -> bool:
    """Whether snow is too rare in the model, over SNOW_BASELINE, to be shown."""
    return snow_days(store, "cordex", cell, *SNOW_BASELINE)[0] < thresholds.SNOW_RARE_DAYS


def on_ground(store: Store, period: Period, cell: Cell, start: date, end: date) -> list[bool | None] | None:
    """Whether there is snow on the ground on each day of start..end, or None
    where it is not shown: where it is not counted, and, for simulated days,
    where the model has too little of it (the figure of the diagram is then
    "rare" too). The stock runs from the 1 August before ``start``, in the same
    source; the days before the first 1 August the source holds are left null."""
    if not counted(store, cell) or (period.source == "cordex" and rare(store, cell)):
        return None
    held = max(store.first[name] for name in (period.source, FINE[period.source]) if name in store.first)
    origin = date(start.year - (start.month < thresholds.SNOW_RESET_MONTH), thresholds.SNOW_RESET_MONTH, 1)
    while origin < held:
        origin = date(origin.year + 1, origin.month, 1)
    out: list[bool | None] = [None] * ((end - start).days + 1)
    if origin > end:
        return out
    values = store.values(period.source, cell, origin, end, ("tas", "pr"))
    ground = snow.on_ground(values["tas"], values["pr"], origin).tolist()
    skipped = max((origin - start).days, 0)
    out[skipped:] = ground[max((start - origin).days, 0):]
    return out


def snows(store: Store, cell: Cell, period: Period, first: int, last: int,
          ref_first: int, ref_last: int) -> tuple[ClimateSnow | None, ClimateSnow | None]:
    """Snow on the ground over the window and over the reference, or nothing
    where it is not counted."""
    if not counted(store, cell):
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
    shown = months(store, period.source, cell, first, last)
    reference_months = months(store, normals.SOURCE, cell, ref_start.year, ref_end.year)
    return Climate(
        snow=own,
        reference_snow=ref,
        koppen=class_of(shown),
        reference_koppen=class_of(reference_months),
        window=ClimateWindow(
            start_year=first,
            end_year=last,
            origin="simulated" if period.source == "cordex" else "observed",
            source=source(store, period.source, cell),
        ),
        months=shown,
        reference=ClimateWindow(
            start_year=ref_start.year,
            end_year=ref_end.year,
            origin="observed",
            source=source(store, normals.SOURCE, cell),
        ),
        reference_months=reference_months,
    )


def class_of(diagram: list[ClimateMonth]) -> str | None:
    """The Köppen-Geiger class of the twelve months the diagram draws."""
    return koppen.of_place([m.temperature_mean for m in diagram], [m.precipitation for m in diagram])


def _mean(values: np.ndarray) -> float | None:
    ok = values[~np.isnan(values)]
    return float(ok.mean()) if ok.size else None
