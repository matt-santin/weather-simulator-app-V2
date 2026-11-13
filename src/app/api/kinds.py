"""Cool, normal and warm seasons of an epoch, at a place.

The form of the home page lets the visitor ask for "a warm summer of the
future climate" rather than for a year. The years of each epoch (EPOCHS) are
ranked by the mean of the daily maximum temperature (tasmax) over the dates of
the season, at the place: the coolest SHARE are "cool", the warmest SHARE are
"warm", the rest "normal". The browser then draws one year at random in the
category asked for.

Each epoch is ranked on its own, on the raw values: within an epoch of 40 or
50 years the trend weighs in the ranking (a warm season of the future climate
falls mostly late in the century), a simplification accepted on 5/11/2026.
The old climate is past data (E-OBS for the temperatures), the future climate
the corrected simulation; the new climate mixes both (2011-2025, then
2027-2050), and the corrected model being cooler than the past data over
2015-2025, its ranking mixes variability and that step (origin null). A year
whose dates fall outside one served period (2026, a winter running into 2026
or 2101) is left out. Epochs, share and criterion are choices of this project
(4 and 5/11/2026).

Each epoch also names its two extreme days over the same dates (7/11/2026): the
hottest day (highest tasmax) and the coldest night (lowest tasmin), with their
date, for "the hottest day" and "the coldest day" of the form. The later one on
a tie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from src.app.api.contract import Kinds, KindsEpoch, Peak
from src.app.api.years import season, whole
from src.app.domain.records import Origin
from src.app.store import Cell, Store

NAME = "tasmax"
COLD = "tasmin"  # the coldest night
SHARE = 0.2  # coolest and warmest share of the years of an epoch


@dataclass(frozen=True)
class Epoch:
    id: str
    first: int
    last: int


EPOCHS = (
    Epoch("old", 1970, 2010),
    Epoch("new", 2011, 2050),
    Epoch("future", 2051, 2100),
)
DEFAULT = "new"


def split(values: dict[int, float]) -> tuple[list[int], list[int], list[int]]:
    """The years ranked by value: (cool, normal, warm), each in calendar order.

    round(SHARE * n) years at each end, one at least: 8 of 41, 10 of 50.
    """
    ranked = sorted(values, key=lambda year: (values[year], year))
    k = max(1, round(SHARE * len(ranked)))
    if 2 * k >= len(ranked):
        return [], sorted(ranked), []
    return sorted(ranked[:k]), sorted(ranked[k:-k]), sorted(ranked[-k:])


def run(store: Store, cell: Cell, start: date, end: date) -> Kinds:
    series = whole(store, cell, (NAME, COLD))

    def chunks(year: int):
        """The source, the first day and both series of the season of `year`."""
        first, _, source, values = season(series, start, end, year)
        return None if source is None else (source, first, values)

    def measure(year: int) -> tuple[str, float] | None:
        found = chunks(year)
        if found is None or not np.isfinite(found[2][NAME]).any():
            return None
        return found[0], float(np.nanmean(found[2][NAME]))

    def peak(years, name: str, sign: int) -> Peak | None:
        """The day of the highest (sign 1) or lowest (sign -1) value of `name`."""
        best = None
        for year in years:
            found = chunks(year)
            if found is None:
                continue
            _, first, values = found
            v = sign * values[name]
            if not np.isfinite(v).any():
                continue
            k = int(np.nanargmax(v))
            if best is None or v[k] >= best[0]:
                best = (float(v[k]), year, first + timedelta(days=k))
        if best is None:
            return None
        return Peak(year=best[1], date=best[2], value=round(sign * best[0], 1))

    epochs = []
    for epoch in EPOCHS:
        measured = {y: measure(y) for y in range(epoch.first, epoch.last + 1)}
        measured = {y: m for y, m in measured.items() if m is not None}
        values = {y: v for y, (_, v) in measured.items()}
        cool, normal, warm = split(values)
        sources = {s for s, _ in measured.values()}
        epochs.append(KindsEpoch(
            id=epoch.id,
            first=epoch.first,
            last=epoch.last,
            origin=None if len(sources) != 1 else
            Origin.SIMULATED if sources == {"cordex"} else Origin.OBSERVED,
            cool=cool,
            normal=normal,
            warm=warm,
            values={y: round(v, 1) for y, v in sorted(values.items())},
            hottest=peak(sorted(values), NAME, 1),
            coldest=peak(sorted(values), COLD, -1),
        ))
    return Kinds(epochs=epochs)
