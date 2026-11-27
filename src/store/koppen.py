"""The two Köppen-Geiger maps of the page /climats, written once as static files.

The classes of 1991-2020 (past data) and of 2071-2100 (the corrected
simulation), over the box of the map page (src.store.outlines.BOX), on the
0.1 deg grid of the temperatures, as the climate block of the results computes
them (src.app.api.climate, src.app.domain.koppen): monthly mean temperature of
the 0.1 deg cell, rain of the 0.25 deg cell nearest to it. The temperatures
are those of the cell, not brought to the altitude of a place. Where the
store has no 0.1 deg cell (small islands), the 0.25 deg cell holding the point
gives both, on land only (the land mask of the map store).

Written to web/static/geo/:
  - koppen_1991-2020.png, koppen_2071-2100.png: one 8-bit grey pixel per cell,
    row 0 to the north, the class as numbered in the legend of Beck et al. 2023
    (data/koppen/beck2023/legend.txt), 0 for no class (sea, outside);
  - koppen.json: the grid (north, west, step, rows, cols, the centres of the
    first row and column), the periods and their files.

    caffeinate -i ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python -m src.store.koppen

About 10 minutes, reading the point store bands of two rows at a time.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import zarr
from PIL import Image

from src.app.domain import koppen
from src.config import DATA
from src.store.outlines import BOX

ROOT = Path(__file__).resolve().parents[2]
POINT = DATA / "serve" / "point.zarr"
MAP = DATA / "serve" / "map.zarr"
OUT = ROOT / "web" / "static" / "geo"
EPOCH = date(1970, 1, 1)
# (label, coarse group, fine group, first year, last year)
PERIODS = [
    ("1991-2020", "era5", "era5land", 1991, 2020),
    ("2071-2100", "cordex", "cordex010", 2071, 2100),
]
# The numbers of the legend of Beck et al. 2023: they are what the PNG holds.
CODES = ["", "Af", "Am", "Aw", "BWh", "BWk", "BSh", "BSk", "Csa", "Csb", "Csc", "Cwa", "Cwb", "Cwc",
         "Cfa", "Cfb", "Cfc", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc", "Dwd", "Dfa", "Dfb",
         "Dfc", "Dfd", "ET", "EF"]
NUMBER = {code: k for k, code in enumerate(CODES) if code}


def calendar(first: int, last: int) -> tuple[np.ndarray, np.ndarray, slice]:
    """The month of each day of first..last, the mean length of each month, the days in the store."""
    start, end = date(first, 1, 1), date(last, 12, 31)
    n = (end - start).days + 1
    month = np.array([(start + timedelta(days=k)).month for k in range(n)])
    length = np.array([(month == m).sum() / (last - first + 1) for m in range(1, 13)])
    return month, length, slice((start - EPOCH).days, (end - EPOCH).days + 1)


def monthly(array, days: slice, rows: slice, cols: slice, month: np.ndarray) -> np.ndarray:
    """The mean of each month (12, rows, cols), in the stored unit, NaN without a value."""
    raw = array[days, rows, cols]
    values = np.where(raw == array.attrs["_FillValue"], np.nan, raw.astype(np.float32) * array.attrs["scale_factor"])
    with np.errstate(invalid="ignore"), np.testing.suppress_warnings() as quiet:
        quiet.filter(RuntimeWarning)
        return np.stack([np.nanmean(values[month == m], axis=0) for m in range(1, 13)])


def classes(T: np.ndarray, P: np.ndarray) -> np.ndarray:
    """The legend numbers of (12, ...) temperatures and rains, 0 where a month is missing."""
    shape = T.shape[1:]
    code = koppen.classify(T.reshape(12, -1), P.reshape(12, -1))
    return np.array([NUMBER.get(str(c), 0) for c in code], dtype=np.uint8).reshape(shape)


def build() -> None:
    point = zarr.open_group(POINT, mode="r")
    lat, lon = point["latitude"][:], point["longitude"][:]
    lat10, lon10 = point["latitude010"][:], point["longitude010"][:]
    fine = point["domain010"][:].astype(bool)
    land = zarr.open_group(MAP, mode="r")["land"][:].astype(bool)
    step = 0.1
    r0 = int(np.argmin(np.abs(lat10 - BOX["north"])))
    r1 = int(np.argmin(np.abs(lat10 - BOX["south"]))) + 1
    c0 = int(np.argmin(np.abs(lon10 - BOX["west"])))
    c1 = int(np.argmin(np.abs(lon10 - BOX["east"]))) + 1
    rows, cols = r1 - r0, c1 - c0
    # The 0.25 deg cell nearest to each 0.1 deg cell: its rain, and its class where there is no fine cell.
    ci = np.clip(np.rint((lat[0] - lat10[r0:r1]) / 0.25).astype(int), 0, lat.size - 1)
    cj = np.clip(np.rint((lon10[c0:c1] - lon[0]) / 0.25).astype(int), 0, lon.size - 1)
    meta = {
        "north": float(lat10[r0]), "west": float(lon10[c0]), "step": step, "rows": rows, "cols": cols,
        "source": "src/store/koppen.py", "built": time.strftime("%Y-%m-%d %H:%M"),
        "codes": CODES, "periods": [],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    for label, coarse, fine_group, first, last in PERIODS:
        t0 = time.time()
        month, length, days = calendar(first, last)
        # The coarse grid whole: rain everywhere, and the classes of the cells without a fine one.
        cr = slice(int(ci.min()), int(ci.max()) + 1)
        cc = slice(int(cj.min()), int(cj.max()) + 1)
        rain = monthly(point[coarse]["pr"], days, cr, cc, month) * length[:, None, None]
        coarse_class = classes(monthly(point[coarse]["tas"], days, cr, cc, month), rain)
        out = np.zeros((rows, cols), np.uint8)
        for r in range(r0 - r0 % 2, r1, 2):
            band = slice(max(r, r0), min(r + 2, r1))
            if not fine[band, c0:c1].any():
                continue
            T = monthly(point[fine_group]["tas"], days, band, slice(c0, c1), month)
            P = rain[:, ci[band.start - r0:band.stop - r0, None] - cr.start, cj[None, :] - cc.start]
            out[band.start - r0:band.stop - r0] = classes(T, P)
            if (r - r0) % 40 == 0:
                print(f"  {label} : lignes {band.stop - r0}/{rows}, {time.time() - t0:.0f} s", flush=True)
        out[~fine[r0:r1, c0:c1]] = 0
        # No fine cell: the coarse class, on land.
        holes = ~fine[r0:r1, c0:c1] & land[ci[:, None], cj[None, :]]
        out[holes] = coarse_class[ci[:, None] - cr.start, cj[None, :] - cc.start][holes]
        name = f"koppen_{label}.png"
        Image.fromarray(out, mode="L").save(OUT / name, optimize=True)
        meta["periods"].append({"label": label, "file": name, "origin": "observed" if coarse == "era5" else "simulated"})
        print(f"{label} : {OUT / name}, {(OUT / name).stat().st_size // 1024} ko, {time.time() - t0:.0f} s", flush=True)
    (OUT / "koppen.json").write_text(json.dumps(meta, ensure_ascii=False))
    print("écrit", OUT / "koppen.json")


if __name__ == "__main__":
    sys.exit(build())
