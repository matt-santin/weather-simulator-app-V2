"""The summary of a search: a few figures of the dates shown, beside their normal.

For the dates of the search, and for the same dates in each year of a
reference period of the normals (normals.REFERENCES, past data, same cells),
this computes:

- the mean of the daily maximum (tasmax), of the daily mean (tas);
- counts of days, with the thresholds of DRIAS (Météo-France, list of
  indicators of 1/12/2023): Tx >= 35 °C (TX35), Tn > 20 °C (TR, tropical
  nights), Tx > 25 °C (SD, summer days), Tn < 0 °C (TNFD, frost days); and
  Tx >= 40 °C, a threshold of this project, not of DRIAS;
- the rain over the dates (mean daily rain x days, as years.py).

The normal of each figure is its mean over the reference years. The server
does not choose which figures a season shows: the page does (summary.js).
"""

from __future__ import annotations

from datetime import date

import numpy as np

from src.app.api import normals
from src.app.api.contract import SeasonRank, Summary, SummaryFigure, rounded
from src.app.api.years import FIRST, LAST, season, shifted, whole
from src.app.store import PERIODS, Cell, Store

NAMES = ("tasmax", "tasmin", "tas", "pr")

# name: (variable, test), thresholds in °C. DRIAS's inequalities, kept as written.
COUNTS = {
    "hot_35": ("tasmax", lambda v: v >= 35.0),
    "hot_40": ("tasmax", lambda v: v >= 40.0),
    "tropical_nights": ("tasmin", lambda v: v > 20.0),
    "summer_days": ("tasmax", lambda v: v > 25.0),
    "frost_days": ("tasmin", lambda v: v < 0.0),
}


def figures(values: dict[str, np.ndarray]) -> dict[str, float | None]:
    """Every figure of one stretch of days; None where a variable is all gaps."""
    out: dict[str, float | None] = {}
    for key, name in (("tasmax_mean", "tasmax"), ("tas_mean", "tas")):
        v = values[name]
        out[key] = float(np.nanmean(v)) if np.isfinite(v).any() else None
    for key, (name, test) in COUNTS.items():
        v = values[name]
        ok = np.isfinite(v)
        # A gap is not a day under or over the threshold: the count is scaled to
        # the whole stretch, as the rain is.
        out[key] = float(test(v[ok]).sum()) * v.size / ok.sum() if ok.any() else None
    p = values["pr"]
    out["precipitation"] = float(np.nanmean(p)) * p.size if np.isfinite(p).any() else None
    return out


def read(store: Store, cell: Cell, start: date, end: date) -> dict[str, np.ndarray] | None:
    for period in PERIODS:
        if period.holds(start, end):
            return store.values(period.source, cell, start, end, NAMES)
    return None


NAMED = 3  # the warmer years are named when there are no more than this


def rank(store: Store, cell: Cell, start: date, end: date) -> SeasonRank | None:
    """The dates shown among the same dates of every observed year, by the mean
    of the daily maximum (the criterion of kinds.py): how many of those years
    were warmer. The year shown, if observed, is not compared with itself. A
    simulated season is thus set against what was lived, not against the model."""
    series = whole(store, cell, ("tasmax",))
    means: dict[int, tuple[str, float]] = {}
    for year in range(FIRST, LAST + 1):
        _, _, source, values = season(series, start, end, year)
        if source is not None and np.isfinite(values["tasmax"]).any():
            means[year] = (source, float(np.nanmean(values["tasmax"])))
    if start.year not in means:
        return None
    shown = means[start.year][1]
    observed = {y: v for y, (source, v) in means.items() if source == normals.SOURCE and y != start.year}
    if not observed:
        return None
    warmer = sorted(y for y, v in observed.items() if v > shown)
    return SeasonRank(first=min(observed), last=max(observed), total=len(observed),
                      warmer=len(warmer), warmer_years=warmer if len(warmer) <= NAMED else [])


def run(store: Store, cell: Cell, start: date, end: date, reference: int) -> Summary:
    shown = read(store, cell, start, end)
    now = figures(shown) if shown is not None else {}

    ref_start, ref_end = normals.reference(reference)
    # One year past the reference: a winter of its last year ends in the next.
    last_read = min(date(ref_end.year + 1, 12, 31), PERIODS[0].end)
    era5 = store.values(normals.SOURCE, cell, ref_start, last_read, NAMES)
    per_year = []
    for year in range(reference, reference + normals.YEARS):
        first, last = shifted(start, end, year)
        k0, k1 = (first - ref_start).days, (last - ref_start).days + 1
        if k1 > len(era5["tas"]):
            continue
        per_year.append(figures({n: era5[n][k0:k1] for n in NAMES}))

    out = {}
    for key in now:
        normal = [f[key] for f in per_year if f[key] is not None]
        out[key] = SummaryFigure(
            value=rounded(now[key]),
            normal=rounded(float(np.mean(normal))) if normal else None,
        )
    return Summary(reference_start=ref_start, reference_end=ref_end, figures=out,
                   rank=rank(store, cell, start, end))
