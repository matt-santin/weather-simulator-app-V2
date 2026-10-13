"""From the store to the JSON contract: read, transform, classify.

1. The period's source is read at the place's cells (temperatures at 0.1 deg
   where there is a cell, the rest at 0.25 deg), and turned into daily records
   (wind from m/s to km/h).
2. The transformation block, neutral by default.
3. The sky class, the temperature bands and the wet bulb, one function each,
   the same for ERA5 and CORDEX days.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.app.api.contract import Day, Grid, Series
from src.app.domain.records import DailyRecord, Origin
from src.app.domain.sky import classify_record
from src.app.store import FIELDS, PERIODS, Cell, Period, Store
from src.app.transform import block

KMH = 3.6


def source(store: Store, period: Period, cell: Cell) -> str:
    """Which dataset served a day, without and with the 0.1 deg temperatures."""
    if period.source == "cordex":
        name = store.simulation.source
        return f"{name}, températures à 0,1°" if cell.fine is not None else name
    return store.datasets(period.source, cell)


def records(store: Store, period: Period, cell: Cell, start: date, end: date):
    values = store.series(period.source, cell, start, end)
    wind = values["sfcWind"]
    values["sfcWind"] = [None if v is None else v * KMH for v in wind]
    origin = Origin.SIMULATED if period.source == "cordex" else Origin.OBSERVED
    n = (end - start).days + 1
    return [
        DailyRecord(
            date=start + timedelta(days=k),
            origin=origin,
            source=source(store, period, cell),
            **{field: values[name][k] for name, field in FIELDS.items()},
        )
        for k in range(n)
    ]


def grid(store: Store, cell: Cell) -> Grid:
    cordex = next(p for p in PERIODS if p.source == "cordex")
    fine = cell.fine is not None
    return Grid(
        model=store.simulation.model,
        reference=store.datasets(cordex.source, cell),
        temperature_step=round(float(abs(store.latitude010[1] - store.latitude010[0])), 2)
        if fine else None,
        calibration_start=store.simulation.calibration_start,
        calibration_end=store.simulation.calibration_end,
        projection_start=cordex.start,
        projection_end=cordex.end,
        step=float(abs(store.latitude[1] - store.latitude[0])),
        generated=date.fromisoformat(store.built[:10]),
    )


def run(store: Store, period: Period, cell: Cell, start: date, end: date) -> Series:
    transformed = block.apply(records(store, period, cell, start, end))
    days = [Day.from_record(r, classify_record(r)) for r in transformed]
    simulated = period.source == "cordex"
    latitude, longitude = store.position(cell)
    return Series(
        latitude=latitude,
        longitude=longitude,
        start=days[0].date,
        end=days[-1].date,
        has_simulated=simulated,
        humid_heat_peak=max((d.humid_heat or 0 for d in days), default=0),
        grid=grid(store, cell) if simulated else None,
        days=days,
    )
