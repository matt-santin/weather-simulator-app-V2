"""The map store (src.store.maps), read a few days over Europe at a time.

The map shows the land cells of the 0.25 deg grid inside BOX (the box of the
country outlines, web/static/geo/europe.json). Their list is fixed: the
browser receives it once (`cells`), then each map as the values of those
cells, day after day, in the store's integers.

The store is optional: without data/serve/map.zarr the site runs and the map
page says it has no data. An unfinished array (no `built`) counts as absent.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import numpy as np
import zarr

from src.config import DATA
from src.store.maps import SOURCES

STORE = Path(os.environ.get("WSA_MAP_STORE", DATA / "serve" / "map.zarr"))
BOX = {"west": -25.0, "east": 45.0, "south": 34.0, "north": 72.0}
VARIABLES = ("tasmax", "tasmin", "pr", "clt")
FILL = -32768  # no value, in the integers served


class MapStore:
    def __init__(self, path: Path = STORE) -> None:
        root = zarr.open_group(path, mode="r")
        lat, lon = root["latitude"][:], root["longitude"][:]
        land = root["land"][:].astype(bool)
        inside = ((lat[:, None] >= BOX["south"]) & (lat[:, None] <= BOX["north"])
                  & (lon[None, :] >= BOX["west"]) & (lon[None, :] <= BOX["east"]))
        self.rows, self.cols = np.nonzero(land & inside)
        self.latitude, self.longitude = lat, lon
        self.step = float(abs(lat[1] - lat[0]))
        # A variable is served when both its periods are built; the others wait.
        self.arrays: dict[tuple[str, str], zarr.Array] = {}
        self.variables = []
        for name in VARIABLES:
            found = {s: root[s][name] for s in SOURCES if s in root and name in root[s]}
            if len(found) == len(SOURCES) and all("built" in a.attrs for a in found.values()):
                self.variables.append(name)
                self.arrays.update({(s, name): a for s, a in found.items()})
        if not self.variables:
            raise RuntimeError(f"{path}: aucune variable complete")

    def cells(self) -> dict:
        """The cells of every map: their rows and columns on the grid, and the grid."""
        return {
            "north": float(self.latitude[0]),
            "west": float(self.longitude[0]),
            "step": self.step,
            "rows": self.rows.tolist(),
            "cols": self.cols.tolist(),
            "variables": self.variables,
        }

    def read(self, source: str, name: str, start: date, end: date) -> np.ndarray:
        """Days x cells in tenths of the stored unit (deg C, mm, %), as little-endian
        16-bit integers, FILL where there is no value. The store keeps int16 for
        the temperatures and uint16 for rain and cloud cover, in hundredths or
        tenths: they are widened before being rescaled."""
        arr = self.arrays[source, name]
        first = date.fromisoformat(arr.attrs["start"])
        k0, k1 = (start - first).days, (end - first).days + 1
        raw = arr[k0:k1][:, self.rows, self.cols]
        missing = raw == arr.attrs["_FillValue"]
        tenths = np.round(raw.astype("float64") * (arr.attrs["scale_factor"] / 0.1))
        tenths[missing] = FILL
        return tenths.astype("<i2")


def open_store(path: Path = STORE) -> MapStore | None:
    try:
        return MapStore(path)
    except (FileNotFoundError, KeyError, RuntimeError):
        return None
