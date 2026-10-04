"""Every year from 1970 to 2100 at a place: the dates of the search, year by year.

Each year carries the mean temperature (tas) and the rain over the same
calendar dates as the search, its source (ERA5 to 2025, corrected CORDEX from
2027), and how it compares with a reference period of the normals
(normals.REFERENCES), always ERA5:

- temperature: the anomaly, in degrees and in standard deviations of the
  reference years (interannual, ddof=1). Under 0.5 sigma: near normal; from
  0.5: warmer or colder; from 1.5: much warmer or much colder;
- rain: the ratio to the reference mean. Under 0.5: much drier; under 0.8:
  drier; up to 1.2: near normal; up to 1.5: wetter; above: much wetter.

The thresholds are a choice of this project, not a standard.

A year whose dates fall outside one served period (2026, a winter running into
2026 or past 2100) is listed with no values.
"""

from __future__ import annotations

from datetime import date

import numpy as np

from src.app.api import normals
from src.app.api.contract import YearSummary, Years
from src.app.domain.records import Origin
from src.app.store import PERIODS, Cell, Store

FIRST, LAST = 1970, 2100
NAMES = ("tas", "pr")
NEAR, MUCH = 0.5, 1.5  # standard deviations


def shifted(start: date, end: date, year: int) -> tuple[date, date]:
    """The same calendar dates in another year; 29 February becomes the 28th."""
    def move(day: date, to: int) -> date:
        try:
            return day.replace(year=to)
        except ValueError:
            return day.replace(year=to, day=28)
    return move(start, year), move(end, year + end.year - start.year)


def temperature_class(sigmas: float) -> str:
    if abs(sigmas) < NEAR:
        return "near"
    side = "warmer" if sigmas > 0 else "colder"
    return f"much_{side}" if abs(sigmas) >= MUCH else side


def rain_class(ratio: float) -> str:
    if ratio < 0.5:
        return "much_drier"
    if ratio < 0.8:
        return "drier"
    if ratio <= 1.2:
        return "near"
    if ratio <= 1.5:
        return "wetter"
    return "much_wetter"


def run(store: Store, cell: Cell, start: date, end: date, reference: int) -> Years:
    series = {}
    for period in PERIODS:
        values = store.series(period.source, cell, period.start, period.end, NAMES)
        series[period.source] = (period, {n: np.array(values[n], dtype=float) for n in NAMES})

    def measure(year: int):
        first, last = shifted(start, end, year)
        for period, values in series.values():
            if period.holds(first, last):
                k0, k1 = (first - period.start).days, (last - period.start).days + 1
                t, p = values["tas"][k0:k1], values["pr"][k0:k1]
                temperature = float(np.nanmean(t)) if np.isfinite(t).any() else None
                # Mean daily rain x days: a missing day does not count as a dry one.
                rain = float(np.nanmean(p)) * p.size if np.isfinite(p).any() else None
                return first, last, period.source, temperature, rain
        return first, last, None, None, None

    measured = {year: measure(year) for year in range(FIRST, LAST + 1)}

    ref_years = [measured[y] for y in range(reference, reference + normals.YEARS)]
    t_ref = np.array([m[3] for m in ref_years if m[3] is not None])
    p_ref = np.array([m[4] for m in ref_years if m[4] is not None])
    t_normal, sigma = float(t_ref.mean()), float(t_ref.std(ddof=1))
    p_normal = float(p_ref.mean())

    years = []
    for year, (first, last, source, temperature, rain) in measured.items():
        anomaly = None if temperature is None else temperature - t_normal
        ratio = None if rain is None or p_normal == 0 else rain / p_normal
        years.append(YearSummary(
            year=year,
            start=first,
            end=last,
            origin=None if source is None else
            Origin.SIMULATED if source == "cordex" else Origin.OBSERVED,
            temperature_mean=_round(temperature),
            temperature_anomaly=_round(anomaly),
            temperature_sigmas=None if anomaly is None or sigma == 0 else round(anomaly / sigma, 2),
            temperature_class=None if anomaly is None or sigma == 0 else temperature_class(anomaly / sigma),
            precipitation=_round(rain),
            precipitation_ratio=None if ratio is None else round(ratio, 2),
            precipitation_class=None if ratio is None else rain_class(ratio),
        ))
    ref_start, ref_end = normals.reference(reference)
    return Years(
        reference_start=ref_start,
        reference_end=ref_end,
        temperature_normal=round(t_normal, 1),
        temperature_sigma=round(sigma, 2),
        precipitation_normal=round(p_normal, 1),
        years=years,
    )


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)
