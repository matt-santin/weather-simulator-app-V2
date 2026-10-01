"""From the store to the JSON contract: read, transform, classify.

1. The period's source is read at the nearest cell, and turned into daily
   records (wind from m/s to km/h).
2. The transformation block, neutral by default.
3. The sky class, the temperature bands and the wet bulb, one function each,
   the same for ERA5 and CORDEX days.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.app.api.contract import Day, Grid, Series
from src.app.domain.records import DailyRecord, Origin
from src.app.domain.sky import classify_record
from src.app.store import FIELDS, PERIODS, Period, Store
from src.app.transform import block

KMH = 3.6
SOURCES = {"era5": "ERA5", "cordex": "CORDEX EUR-11 corrigé"}
MODEL = "EC-EARTH (r12i1p1) / SMHI-RCA4, CORDEX EUR-11, scénario RCP 4.5"
CALIBRATION = (date(1970, 1, 1), date(2005, 12, 31))


def records(store: Store, period: Period, cell: tuple[int, int], start: date, end: date):
    values = store.series(period.source, cell, start, end)
    wind = values["sfcWind"]
    values["sfcWind"] = [None if v is None else v * KMH for v in wind]
    origin = Origin.SIMULATED if period.source == "cordex" else Origin.OBSERVED
    n = (end - start).days + 1
    return [
        DailyRecord(
            date=start + timedelta(days=k),
            origin=origin,
            source=SOURCES[period.source],
            **{field: values[name][k] for name, field in FIELDS.items()},
        )
        for k in range(n)
    ]


def grid(store: Store) -> Grid:
    cordex = next(p for p in PERIODS if p.source == "cordex")
    return Grid(
        model=MODEL,
        calibration_start=CALIBRATION[0],
        calibration_end=CALIBRATION[1],
        projection_start=cordex.start,
        projection_end=cordex.end,
        step=float(abs(store.latitude[1] - store.latitude[0])),
        generated=date.fromisoformat(store.built[:10]),
    )


def run(store: Store, period: Period, cell: tuple[int, int], start: date, end: date) -> Series:
    transformed = block.apply(records(store, period, cell, start, end))
    days = [Day.from_record(r, classify_record(r)) for r in transformed]
    simulated = period.source == "cordex"
    i, j = cell
    return Series(
        latitude=float(store.latitude[i]),
        longitude=float(store.longitude[j]),
        start=days[0].date,
        end=days[-1].date,
        has_simulated=simulated,
        humid_heat_peak=max((d.humid_heat or 0 for d in days), default=0),
        grid=grid(store) if simulated else None,
        days=days,
    )
