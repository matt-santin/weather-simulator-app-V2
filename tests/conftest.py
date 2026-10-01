"""A small store with the layout of src.store.build, so that the API is tested
without the real one (20 GB, built from the external drive).

5 x 5 cells at 0.25 deg around Grenoble, the north-west corner outside the
domain. Every variable holds its day index since the source's first day, times
the step, modulo 3000: a value tells which day was read. One precipitation day
is a gap.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
import zarr

LATITUDE = np.array([46.0, 45.75, 45.5, 45.25, 45.0])
LONGITUDE = np.array([5.0, 5.25, 5.5, 5.75, 6.0])
SOURCES = {"era5": (date(1970, 1, 1), date(2005, 12, 31)), "cordex": (date(1970, 1, 1), date(2100, 12, 31))}
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


def fill(dtype: str) -> int:
    return int(np.iinfo(dtype).min if dtype == "int16" else np.iinfo(dtype).max)


def expected(source: str, day: date, name: str) -> float:
    """The value the small store holds for that day, in its stored unit."""
    return ((day - SOURCES[source][0]).days % 3000) * VARIABLES[name][1]


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
    return path
