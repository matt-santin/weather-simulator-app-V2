"""The serving store (src.store.build), read point by point.

Two sources, each serving one period:

- era5: the ERA5 reanalysis, 1970-2025, days that happened;
- cordex: corrected CORDEX, 2027-2100, a plausible trajectory, not a forecast.

2026 is served by neither: the year is not over in ERA5, and CORDEX there
would show a fictional weather for a year the visitor remembers.

Two grids. Everything at 0.25 deg; the temperatures also at 0.1 deg, over
land (era5land and cordex010, corrected against ERA5-Land), which keeps the
relief the coarse grid smooths. A place takes its temperatures from the
nearest 0.1 deg cell if one lies within FINE_RADIUS (99.9 % of the coarse
cells that are mostly land have one; small islands and the sea do not), and
from its 0.25 deg cell otherwise. Without the 0.1 deg arrays, the store serves
0.25 deg everywhere.

zarr is read directly rather than through xarray: the server needs integer
chunks and three attributes, and importing xarray and pandas would double its
start-up time. A series costs one chunk per variable, whatever its length.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import zarr

from src.config import DATA

STORE = Path(os.environ.get("WSA_STORE", DATA / "serve" / "point.zarr"))

# Stored name to the field of the daily record.
FIELDS = {
    "tasmax": "temperature_max",
    "tasmin": "temperature_min",
    "tas": "temperature_mean",
    "pr": "precipitation",
    "clt": "cloud_cover",
    "hurs": "relative_humidity_mean",
    "sfcWind": "wind_speed_mean",
}

EPOCH = date(1970, 1, 1)
TEMPERATURES = ("tasmax", "tasmin", "tas")
FINE = {"era5": "era5land", "cordex": "cordex010"}
FINE_RADIUS = 0.1  # degrees, in latitude and in longitude


@dataclass(frozen=True)
class Period:
    source: str
    start: date
    end: date

    def holds(self, start: date, end: date) -> bool:
        return self.start <= start and end <= self.end


PERIODS = (
    Period("era5", date(1970, 1, 1), date(2025, 12, 31)),
    Period("cordex", date(2027, 1, 1), date(2100, 12, 31)),
)


@dataclass(frozen=True)
class Cell:
    """Where a place is read: its 0.25 deg cell, and its 0.1 deg one, if any."""

    coarse: tuple[int, int]
    fine: tuple[int, int] | None


class Store:
    """The arrays, opened once. Missing or unfinished arrays stop the start-up."""

    def __init__(self, path: Path = STORE) -> None:
        root = zarr.open_group(path, mode="r")
        self.latitude = root["latitude"][:]
        self.longitude = root["longitude"][:]
        self.domain = root["domain"][:].astype(bool)
        self.arrays: dict[str, dict[str, zarr.Array]] = {}
        self.first: dict[str, date] = {}
        for period in PERIODS:
            self._open(root, path, period.source, FIELDS, period)
        self.fine = "domain010" in root
        if self.fine:
            self.latitude010 = root["latitude010"][:]
            self.longitude010 = root["longitude010"][:]
            self.domain010 = root["domain010"][:].astype(bool)
            for period in PERIODS:
                self._open(root, path, FINE[period.source], TEMPERATURES, period)
        self.built = max(a.attrs["built"] for g in self.arrays.values() for a in g.values())

    def _open(self, root, path, source, names, period: Period) -> None:
        group = root[source]
        arrays = {}
        for name in names:
            if name not in group:
                raise RuntimeError(f"{path}: {source}/{name} absent")
            arr = group[name]
            if "built" not in arr.attrs:
                raise RuntimeError(f"{path}: {source}/{name} incomplet")
            arrays[name] = arr
        self.arrays[source] = arrays
        time = group["time"]
        if time.attrs["units"] != "days since 1970-01-01 00:00:00":
            raise RuntimeError(f"{path}: {source}/time, unite {time.attrs['units']}")
        self.first[source] = EPOCH + timedelta(days=int(time[0]))
        last = EPOCH + timedelta(days=int(time[-1]))
        if self.first[source] > period.start or last < period.end:
            raise RuntimeError(f"{path}: {source} couvre {self.first[source]}..{last}, "
                               f"la periode servie est {period.start}..{period.end}")

    def cell(self, latitude: float, longitude: float) -> Cell | None:
        """Where to read a place, or None outside the domain."""
        step = abs(self.latitude[1] - self.latitude[0])
        i = int(np.abs(self.latitude - latitude).argmin())
        j = int(np.abs(self.longitude - longitude).argmin())
        if abs(self.latitude[i] - latitude) > step / 2 or abs(self.longitude[j] - longitude) > step / 2:
            return None
        if not self.domain[i, j]:
            return None
        return Cell((i, j), self._fine_cell(latitude, longitude) if self.fine else None)

    def _fine_cell(self, latitude: float, longitude: float) -> tuple[int, int] | None:
        """The nearest 0.1 deg cell with data, within FINE_RADIUS, or None."""
        i = int(np.abs(self.latitude010 - latitude).argmin())
        j = int(np.abs(self.longitude010 - longitude).argmin())
        best, dist = None, None
        for a in range(max(i - 1, 0), min(i + 2, self.latitude010.size)):
            for b in range(max(j - 1, 0), min(j + 2, self.longitude010.size)):
                dlat = abs(self.latitude010[a] - latitude)
                dlon = abs(self.longitude010[b] - longitude)
                if not self.domain010[a, b] or max(dlat, dlon) > FINE_RADIUS + 1e-6:
                    continue
                d = dlat**2 + (dlon * np.cos(np.deg2rad(latitude))) ** 2
                if dist is None or d < dist:
                    best, dist = (a, b), d
        return best

    def position(self, cell: Cell) -> tuple[float, float]:
        """Centre of the cell the temperatures are read at."""
        if cell.fine:
            return float(self.latitude010[cell.fine[0]]), float(self.longitude010[cell.fine[1]])
        return float(self.latitude[cell.coarse[0]]), float(self.longitude[cell.coarse[1]])

    def series(self, source: str, cell: Cell, start: date, end: date,
               names: tuple[str, ...] = tuple(FIELDS)) -> dict[str, list]:
        """Each variable over start..end, in its stored unit, None for a gap. The
        temperatures from the 0.1 deg cell if there is one."""
        out = self._read(source, cell.coarse, start, end, names)
        fine = [n for n in TEMPERATURES if n in names]
        if cell.fine and fine:
            out |= self._read(FINE[source], cell.fine, start, end, fine)
        return out

    def _read(self, source, at, start, end, names) -> dict[str, list]:
        i, j = at
        k0 = (start - self.first[source]).days
        k1 = (end - self.first[source]).days + 1
        out = {}
        for name in names:
            arr = self.arrays[source][name]
            raw = arr[k0:k1, i, j]
            values = raw * arr.attrs["scale_factor"]
            gap = raw == arr.attrs["_FillValue"]
            out[name] = [None if g else round(float(v), 2) for v, g in zip(values, gap, strict=True)]
        return out
