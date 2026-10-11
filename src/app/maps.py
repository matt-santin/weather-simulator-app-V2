"""The map store (src.store.maps), read a few days over Europe at a time.

The map shows the land cells of the 0.25 deg grid inside BOX (the box of the
country outlines, web/static/geo/europe.json). Their list is fixed: the
browser receives it once (`cells`), then each map as the values of those
cells, day after day, in the store's integers.

The sea-level pressure (psl) is not one of the variables: it is drawn as
isobars over any of them, and needs the sea as much as the land. It is served
on its own grid: every cell of BOX, averaged 2 x 2 to 0.5 deg (a season weighs
2 MB, 0.8 MB once compressed), in tenths of a hPa. It is then smoothed, as
published pressure charts are: over land, sea-level pressure is extrapolated
below the ground from the surface pressure, and over the relief (Iberia, the
Alps, Anatolia, Scandinavia) that leaves small loops and wavering lines.

The store is optional: without data/serve/map.zarr the site runs and the map
page says it has no data. An unfinished array (no `built`), or a CORDEX one
that does not say which simulation it holds, counts as absent. The CORDEX
arrays must all hold the same simulation, the one of the point store
(checked at start-up, src.app.api.app).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import numpy as np
import zarr

from src.app.store import Simulation
from src.config import DATA
from src.store.maps import SOURCES

STORE = Path(os.environ.get("WSA_MAP_STORE", DATA / "serve" / "map.zarr"))
BOX = {"west": -25.0, "east": 45.0, "south": 34.0, "north": 72.0}
VARIABLES = ("tasmax", "tasmin", "pr", "clt")
PRESSURE = "psl"
COARSEN = 2  # cells of the store averaged, in latitude and longitude, for the isobars
SMOOTH = 2  # passes of the 1-2-1 filter over the 0.5 deg pressure (1-4-6-4-1, about 1 deg)
FILL = -32768  # no value, in the integers served


class MapStore:
    def __init__(self, path: Path = STORE) -> None:
        root = zarr.open_group(path, mode="r")
        lat, lon = root["latitude"][:], root["longitude"][:]
        land = root["land"][:].astype(bool)
        inside = ((lat[:, None] >= BOX["south"]) & (lat[:, None] <= BOX["north"])
                  & (lon[None, :] >= BOX["west"]) & (lon[None, :] <= BOX["east"]))
        self.rows, self.cols = np.nonzero(land & inside)
        rows = np.nonzero((lat >= BOX["south"]) & (lat <= BOX["north"]))[0]
        cols = np.nonzero((lon >= BOX["west"]) & (lon <= BOX["east"]))[0]
        # Whole blocks of COARSEN x COARSEN cells, from the north-west corner of BOX.
        self.box = (rows[0], rows[0] + rows.size // COARSEN * COARSEN,
                    cols[0], cols[0] + cols.size // COARSEN * COARSEN)
        self.latitude, self.longitude = lat, lon
        self.step = float(abs(lat[1] - lat[0]))
        # A variable is served when both its periods are built; the others wait.
        self.arrays: dict[tuple[str, str], zarr.Array] = {}
        self.variables = []
        for name in VARIABLES:
            found = {s: root[s][name] for s in SOURCES if s in root and name in root[s]}
            if (len(found) == len(SOURCES) and all("built" in a.attrs for a in found.values())
                    and "simulation" in found["cordex"].attrs):
                self.variables.append(name)
                self.arrays.update({(s, name): a for s, a in found.items()})
        if not self.variables:
            raise RuntimeError(f"{path}: aucune variable complete")
        found = {s: root[s][PRESSURE] for s in SOURCES if s in root and PRESSURE in root[s]}
        self.isobars = (len(found) == len(SOURCES) and all("built" in a.attrs for a in found.values())
                        and "simulation" in found["cordex"].attrs)
        if self.isobars:
            self.arrays.update({(s, PRESSURE): a for s, a in found.items()})
        runs = {name: dict(self.arrays["cordex", name].attrs["simulation"])
                for name in self.variables + ([PRESSURE] if self.isobars else [])}
        first = runs[self.variables[0]]
        if any(run != first for run in runs.values()):
            raise ValueError(f"{path}: les grandeurs ne viennent pas toutes de la meme simulation")
        self.simulation = Simulation.read(first)

    def cells(self) -> dict:
        """The cells of every map: their rows and columns on the grid, and the grid."""
        return {
            "north": float(self.latitude[0]),
            "west": float(self.longitude[0]),
            "step": self.step,
            "rows": self.rows.tolist(),
            "cols": self.cols.tolist(),
            "variables": self.variables,
            "isobars": self.isobars,
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


    def pressure(self, source: str, start: date, end: date) -> tuple[np.ndarray, dict]:
        """Days x rows x columns of the 0.5 deg grid over BOX, sea-level pressure
        in tenths of a hPa as little-endian 16-bit integers, FILL where a block
        has a cell without value (outside the CORDEX domain); and the grid: the
        centre of its north-west block and its step, in degrees."""
        arr = self.arrays[source, PRESSURE]
        first = date.fromisoformat(arr.attrs["start"])
        k0, k1 = (start - first).days, (end - first).days + 1
        i0, i1, j0, j1 = self.box
        raw = arr[k0:k1, i0:i1, j0:j1]
        hpa = np.where(raw == arr.attrs["_FillValue"], np.nan, raw * arr.attrs["scale_factor"])
        n, ny, nx = hpa.shape
        blocks = hpa.reshape(n, ny // COARSEN, COARSEN, nx // COARSEN, COARSEN).mean(axis=(2, 4))
        tenths = np.where(np.isnan(blocks), FILL, np.round(smooth(blocks, SMOOTH) * 10))
        half = (COARSEN - 1) * self.step / 2
        grid = {"north": float(self.latitude[i0]) - half, "west": float(self.longitude[j0]) + half,
                "step": COARSEN * self.step}
        return tenths.astype("<i2"), grid


def smooth(field: np.ndarray, passes: int = 1) -> np.ndarray:
    """The 1-2-1 filter along each of the last two axes, `passes` times. A
    missing neighbour (NaN) is left out and the weights of the others
    normalised; a missing value stays missing."""
    out = field.astype("float64")
    missing = np.isnan(out)
    for _ in range(passes):
        for axis in (-2, -1):
            value = np.where(np.isnan(out), 0.0, out)
            weight = np.isfinite(out).astype("float64")
            total, count = 2 * value, 2 * weight
            for shift in (1, -1):
                pad = [(0, 0)] * out.ndim
                pad[axis] = (1, 1)
                sl = [slice(None)] * out.ndim
                sl[axis] = slice(1 + shift, out.shape[axis] + 1 + shift)
                total += np.pad(value, pad)[tuple(sl)]
                count += np.pad(weight, pad)[tuple(sl)]
            with np.errstate(invalid="ignore", divide="ignore"):
                out = np.where(missing, np.nan, total / count)
    return out


def open_store(path: Path = STORE) -> MapStore | None:
    try:
        return MapStore(path)
    except (FileNotFoundError, KeyError, RuntimeError):
        return None
