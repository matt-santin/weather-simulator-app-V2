"""The serving store (src.store.build), read point by point.

Two sources on one 0.25 deg grid, each serving one period:

- era5: the ERA5 reanalysis, 1970-2025, days that happened;
- cordex: corrected CORDEX, 2027-2100, a plausible trajectory, not a forecast.

2026 is served by neither: the year is not over in ERA5, and CORDEX there
would show a fictional weather for a year the visitor remembers.

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
            group = root[period.source]
            arrays = {}
            for name in FIELDS:
                if name not in group:
                    raise RuntimeError(f"{path}: {period.source}/{name} absent")
                arr = group[name]
                if "built" not in arr.attrs:
                    raise RuntimeError(f"{path}: {period.source}/{name} incomplet")
                arrays[name] = arr
            self.arrays[period.source] = arrays
            time = group["time"]
            if time.attrs["units"] != "days since 1970-01-01 00:00:00":
                raise RuntimeError(f"{path}: {period.source}/time, unite {time.attrs['units']}")
            self.first[period.source] = EPOCH + timedelta(days=int(time[0]))
            last = EPOCH + timedelta(days=int(time[-1]))
            if self.first[period.source] > period.start or last < period.end:
                raise RuntimeError(
                    f"{path}: {period.source} couvre {self.first[period.source]}..{last}, "
                    f"la periode servie est {period.start}..{period.end}"
                )
        self.built = max(a.attrs["built"] for g in self.arrays.values() for a in g.values())

    def cell(self, latitude: float, longitude: float) -> tuple[int, int] | None:
        """Indices of the nearest cell, or None outside the domain."""
        step = abs(self.latitude[1] - self.latitude[0])
        i = int(np.abs(self.latitude - latitude).argmin())
        j = int(np.abs(self.longitude - longitude).argmin())
        if abs(self.latitude[i] - latitude) > step / 2 or abs(self.longitude[j] - longitude) > step / 2:
            return None
        return (i, j) if self.domain[i, j] else None

    def series(self, source: str, cell: tuple[int, int], start: date, end: date) -> dict[str, list]:
        """Each variable over start..end at one cell, in its stored unit, None for a gap."""
        i, j = cell
        k0 = (start - self.first[source]).days
        k1 = (end - self.first[source]).days + 1
        out = {}
        for name, arr in self.arrays[source].items():
            raw = arr[k0:k1, i, j]
            values = raw * arr.attrs["scale_factor"]
            gap = raw == arr.attrs["_FillValue"]
            out[name] = [None if g else round(float(v), 2) for v, g in zip(values, gap, strict=True)]
        return out
