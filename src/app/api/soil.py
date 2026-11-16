"""The water left in the soil at a place, day by day.

A daily balance of one reservoir (src.app.domain.soil): rain and snowmelt fill
it, the reference evapotranspiration ET0 (src.app.domain.et0, FAO-56
Penman-Monteith) empties it, slowed down as the soil dries. The cover is the
reference grass and the reservoir holds thresholds.SOIL_CAPACITY_MM everywhere.

ET0 is computed here, from what the store serves at the place: its
temperatures (0.1 deg cell, brought to its altitude when it is given), and the
relative humidity, wind and solar radiation of its 0.25 deg cell. The net
longwave radiation is the FAO estimate (eq. 39): against the Penman-Monteith
ETP of five Meteo-France stations over 1991-2020, ET0 computed this way from
ERA5 is 3 % above to 13 % under, where the downward longwave flux of the
reanalysis minus the emission at air temperature gives 17 to 32 % under
(figures/sol/meteofrance.py).

The balance of a day depends on every day before it. It runs from the first
day the source holds, with a full reservoir, past and simulated days each in
their own series: a simulated day never starts from a past one. The whole
series of a place is kept for the next call.

Without the solar radiation in the store, nothing is computed.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import numpy as np

from src.app.domain import et0, soil, thresholds
from src.app.store import FINE, Cell, Period, Store

RADIATION = "rsds"
NAMES = ("tasmax", "tasmin", "tas", "pr", "hurs", "sfcWind", RADIATION)


def origin(store: Store, source: str) -> date:
    """The first day both grids of the source hold."""
    return max(store.first[name] for name in (source, FINE[source]) if name in store.first)


def reference(store: Store, source: str, cell: Cell, start: date, end: date) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """ET0 of each day of start..end, in mm, and the values it was computed from."""
    v = store.values(source, cell, start, end, NAMES)
    latitude, _ = store.position(cell)
    altitude = (store.elevation(cell) or 0.0) - (cell.lift or 0.0)
    days = np.datetime64(start.isoformat()) + np.arange((end - start).days + 1)
    day_of_year = (days - days.astype("datetime64[Y]")).astype(int) + 1
    rs = v[RADIATION] * et0.MJ_PER_W
    es, ea = et0.vapour(v["tasmax"], v["tasmin"], v["hurs"])
    rso = et0.clear_sky(et0.extraterrestrial(latitude, day_of_year), altitude)
    rn = (1 - et0.ALBEDO) * rs - et0.net_longwave(v["tasmax"], v["tasmin"], ea, rs, rso)
    return et0.reference(v["tasmax"], v["tasmin"], ea, es, et0.wind_2m(v["sfcWind"]), rn,
                         et0.pressure(altitude)), v


@lru_cache(maxsize=64)
def _whole(store: Store, source: str, cell: Cell, last: date) -> soil.Balance:
    """The balance of every day the source holds, up to ``last``."""
    first = origin(store, source)
    demand, v = reference(store, source, cell, first, last)
    return soil.balance(soil.liquid(v["tas"], v["pr"], first), demand, thresholds.SOIL_CAPACITY_MM)


def balance(store: Store, period: Period, cell: Cell) -> tuple[date, soil.Balance] | None:
    """The first day of the balance and the balance, to the end of the served
    period; None where the store has no solar radiation."""
    if not store.has(RADIATION):
        return None
    return origin(store, period.source), _whole(store, period.source, cell, period.end)


def water(store: Store, period: Period, cell: Cell, start: date, end: date) -> list[int | None] | None:
    """Percent of the available water left in the soil at the end of each day
    of start..end; None where it is not computed, null on a day without data."""
    found = balance(store, period, cell)
    if found is None:
        return None
    first, whole = found
    fill = whole.fill[(start - first).days:(end - first).days + 1]
    return [None if f != f else int(round(100 * f)) for f in fill.tolist()]
