"""A small store with the layout of src.store.build, so that the API is tested
without the real one (20 GB, built from the external drive).

5 x 5 cells at 0.25 deg around Grenoble, the north-west corner outside the
domain. Every variable holds its day index since the source's first day, times
the step, modulo 3000: a value tells which day was read. One precipitation day
is a gap.

Beside it, the 0.1 deg grid of the temperatures, 11 x 11 cells over the same
area, holding the same index plus FINE_OFFSET steps, so that a value also tells
which grid was read. Its south-east corner (south of 45.15, east of 5.85) has
no cell: the coarse cell there is served alone.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
import zarr

LATITUDE = np.array([46.0, 45.75, 45.5, 45.25, 45.0])
LONGITUDE = np.array([5.0, 5.25, 5.5, 5.75, 6.0])
SOURCES = {"era5": (date(1970, 1, 1), date(2025, 12, 31)), "cordex": (date(1970, 1, 1), date(2100, 12, 31))}
VARIABLES = {  # name: dtype, step
    "tasmax": ("int16", 0.01),
    "tasmin": ("int16", 0.01),
    "tas": ("int16", 0.01),
    "pr": ("uint16", 0.1),
    "clt": ("uint16", 0.01),
    "hurs": ("uint16", 0.01),
    "sfcWind": ("uint16", 0.01),
}
GAP = date(2044, 7, 14)  # pr missing that day, in cordex
LATITUDE010 = np.round(np.arange(46.0, 44.95, -0.1), 2)
LONGITUDE010 = np.round(np.arange(5.0, 6.05, 0.1), 2)
FINE_OFFSET = 500
FINE = {"era5": "era5land", "cordex": "cordex010"}


def fill(dtype: str) -> int:
    return int(np.iinfo(dtype).min if dtype == "int16" else np.iinfo(dtype).max)


def expected(source: str, day: date, name: str, fine: bool = False) -> float:
    """The value the small store holds for that day, in its stored unit."""
    index = (day - SOURCES[source][0]).days % 3000 + (FINE_OFFSET if fine else 0)
    return index * VARIABLES[name][1]


@pytest.fixture(scope="session")
def store_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("store") / "point.zarr"
    root = zarr.open_group(path, mode="w", zarr_format=3)
    root.create_array("latitude", data=LATITUDE)
    root.create_array("longitude", data=LONGITUDE)
    domain = np.ones((5, 5), dtype="uint8")
    domain[0, 0] = 0
    root.create_array("domain", data=domain)
    for source, (start, end) in SOURCES.items():
        group = root.create_group(source)
        n = (end - start).days + 1
        first = (start - date(1970, 1, 1)).days
        time = group.create_array("time", data=np.arange(first, first + n, dtype="int64"))
        time.attrs["units"] = "days since 1970-01-01 00:00:00"
        index = (np.arange(n) % 3000)[:, None, None] * np.ones((1, 5, 5), dtype="int64")
        for name, (dtype, step) in VARIABLES.items():
            data = index.astype(dtype)
            data[:, 0, 0] = fill(dtype)
            if source == "cordex" and name == "pr":
                data[(GAP - start).days] = fill(dtype)
            arr = group.create_array(name, data=data, chunks=(n, 5, 5))
            arr.attrs.update({"scale_factor": step, "_FillValue": fill(dtype), "built": "2026-09-30 22:00"})

    root.create_array("latitude010", data=LATITUDE010)
    root.create_array("longitude010", data=LONGITUDE010)
    domain010 = np.ones((LATITUDE010.size, LONGITUDE010.size), dtype="uint8")
    domain010[np.ix_(LATITUDE010 < 45.15, LONGITUDE010 > 5.85)] = 0
    root.create_array("domain010", data=domain010)
    shape = (LATITUDE010.size, LONGITUDE010.size)
    for source, (start, end) in SOURCES.items():
        group = root.create_group(FINE[source])
        n = (end - start).days + 1
        first = (start - date(1970, 1, 1)).days
        time = group.create_array("time", data=np.arange(first, first + n, dtype="int64"))
        time.attrs["units"] = "days since 1970-01-01 00:00:00"
        index = (np.arange(n) % 3000 + FINE_OFFSET)[:, None, None] * np.ones((1, *shape), dtype="int64")
        for name in ("tasmax", "tasmin", "tas"):
            data = np.where(domain010[None].astype(bool), index, fill("int16")).astype("int16")
            arr = group.create_array(name, data=data, chunks=(n, *shape))
            arr.attrs.update({"scale_factor": 0.01, "_FillValue": fill("int16"), "built": "2026-10-02 12:00"})
    return path


MAP_SOURCES = {"era5": date(1970, 1, 1), "cordex": date(2027, 1, 1)}
MAP_DAYS = {"era5": 20454, "cordex": 27028}


@pytest.fixture(scope="session")
def map_store_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The layout of src.store.maps on the 5 x 5 grid above: tasmax holds the day
    index since the source's first day (modulo 3000) plus 10 x the cell's row,
    in hundredths. The north-west cell is sea. pr holds the day index in tenths
    of a mm, none on the first day; clt is not built."""
    path = tmp_path_factory.mktemp("maps") / "map.zarr"
    root = zarr.open_group(path, mode="w", zarr_format=3)
    root.create_array("latitude", data=LATITUDE)
    root.create_array("longitude", data=LONGITUDE)
    land = np.ones((5, 5), dtype="uint8")
    land[0, 0] = 0
    root.create_array("land", data=land)
    for source, first in MAP_SOURCES.items():
        n = MAP_DAYS[source]
        data = ((np.arange(n) % 3000)[:, None, None] + 10 * np.arange(5)[None, :, None]
                + np.zeros((1, 1, 5), dtype="int64")).astype("int16")
        arr = root.require_group(source).create_array("tasmax", data=data, chunks=(32, 5, 5))
        arr.attrs.update({"scale_factor": 0.01, "_FillValue": -32768, "start": first.isoformat(),
                          "built": "2026-10-04 21:42"})
        # Rain as the store keeps it: uint16 in tenths of a mm, 65535 for no value.
        rain = ((np.arange(n) % 3000)[:, None, None] + np.zeros((1, 5, 5), dtype="int64")).astype("uint16")
        rain[0] = 65535
        arr = root[source].create_array("pr", data=rain, chunks=(32, 5, 5))
        arr.attrs.update({"scale_factor": 0.1, "_FillValue": 65535, "start": first.isoformat(),
                          "built": "2026-10-04 21:42"})
    return path
