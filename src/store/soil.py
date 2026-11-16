"""Water left in the soil, every day and every cell, for the map store.

    python -m src.store.soil

The soil water balance of the site (src.app.api.soil, src.app.domain.soil) run
over the whole 0.25 deg grid, from the point store (data/serve/point.zarr), and
written to the map store (data/serve/map.zarr) as the variable `soil`: percent
of the available water left at the end of the day, 0 at the wilting point, 100
at field capacity, 8-bit integers, 255 for no value.

The reservoir of each cell is the point store's (src.store.capacity), as for a
place. The same arithmetic as for a place, with one difference: the temperatures are
those of the 0.25 deg cell, where a place takes them from its 0.1 deg cell,
brought to its altitude. A map and a place can therefore differ by a few
points where the relief is marked.

Each balance starts full on the first day of its source in the point store
(1 January 1970, for the past and for the simulation alike) and runs to its
end; the map keeps the days it serves (era5 1970-2025, cordex 2027-2100), as
src.store.maps does.

Computed a quarter of the domain at a time (the chunks of the map store), by
blocks of BLOCK x BLOCK cells (one day after another, every cell of the block
at once): a quarter of cordex holds about 1.1 GB in memory. A block with no
land cell is skipped. The attribute `built` is written last.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from datetime import date, timedelta

import numpy as np
import zarr
from zarr.codecs import BloscCodec

from src.app.domain import et0, soil, thresholds
from src.store.build import STORE as POINT
from src.store.maps import DAYS, EPOCH, SOURCES, STORE

NAME = "soil"
INPUTS = ("tasmax", "tasmin", "tas", "pr", "hurs", "sfcWind", "rsds")
BLOCK = 20
FILL = 255

log = logging.getLogger("soil")
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler())


def read(group: zarr.Group, name: str, rows: slice, cols: slice) -> np.ndarray:
    """Every day of one variable over a block, as floats in its unit, NaN for no value."""
    arr = group[name]
    raw = arr[:, rows, cols]
    out = raw.astype("float64") * arr.attrs["scale_factor"]
    out[raw == arr.attrs["_FillValue"]] = np.nan
    return out.reshape(raw.shape[0], -1)


def capacities(point: zarr.Group) -> np.ndarray:
    """The reservoir of each cell, in mm, as Store.capacity gives it."""
    if "soil_capacity" not in point:
        return np.full(point["domain"].shape, thresholds.SOIL_CAPACITY_MM)
    found = point["soil_capacity"][:].astype("float64")
    return np.where(np.isnan(found), thresholds.SOIL_CAPACITY_MM, found)


def block(group: zarr.Group, first: date, latitude: np.ndarray, altitude: np.ndarray,
          capacity: np.ndarray, rows: slice, cols: slice) -> np.ndarray:
    """Fill of the reservoir, days x cells of the block, from ``first``."""
    v = {name: read(group, name, rows, cols) for name in INPUTS}
    n = v["tas"].shape[0]
    days = np.datetime64(first.isoformat()) + np.arange(n)
    day_of_year = ((days - days.astype("datetime64[Y]")).astype(int) + 1)[:, None]
    lat = np.repeat(latitude[rows], cols.stop - cols.start)[None, :]
    alt = altitude[rows, cols].reshape(1, -1)
    rs = v["rsds"] * et0.MJ_PER_W
    es, ea = et0.vapour(v["tasmax"], v["tasmin"], v["hurs"])
    rso = et0.clear_sky(et0.extraterrestrial(lat, day_of_year), alt)
    rn = (1 - et0.ALBEDO) * rs - et0.net_longwave(v["tasmax"], v["tasmin"], ea, rs, rso)
    demand = et0.reference(v["tasmax"], v["tasmin"], ea, es, et0.wind_2m(v["sfcWind"]), rn, et0.pressure(alt))
    water = soil.liquid_many(v["tas"], v["pr"], first)
    return soil.fill_many(water, demand, capacity[rows, cols].reshape(-1))


def build(point: zarr.Group, source: str) -> None:
    t0 = time.time()
    group = point[source]
    origin = EPOCH + timedelta(days=int(group["time"][0]))
    first, last = SOURCES[source]
    k0, n = (first - origin).days, (last - first).days + 1
    latitude = point["latitude"][:]
    altitude = np.nan_to_num(point["elevation"][:], nan=0.0)  # no altitude known: sea level
    capacity = capacities(point)
    land = zarr.open_group(STORE, mode="r")["land"][:].astype(bool)
    ny, nx = land.shape
    qy, qx = (ny + 1) // 2, (nx + 1) // 2
    shutil.rmtree(STORE / source / NAME, ignore_errors=True)
    arr = zarr.open_group(STORE, mode="a").require_group(source).create_array(
        NAME, shape=(n, ny, nx), dtype="uint8", chunks=(DAYS, qy, qx), fill_value=FILL,
        compressors=[BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")])
    arr.attrs.update({"scale_factor": 1, "_FillValue": FILL, "units": "%", "start": first.isoformat(),
                      "capacity": dict(point["soil_capacity"].attrs) if "soil_capacity" in point
                      else {"units": "mm", "everywhere": thresholds.SOIL_CAPACITY_MM}})
    for key in ("simulation",):
        if key in group["tasmax"].attrs:
            arr.attrs[key] = group["tasmax"].attrs[key]
    arr.attrs["reference"] = group["tasmax"].attrs["reference"]
    done = 0
    for i0 in range(0, ny, qy):
        for j0 in range(0, nx, qx):
            i1, j1 = min(i0 + qy, ny), min(j0 + qx, nx)
            quarter = np.full((n, i1 - i0, j1 - j0), FILL, dtype="uint8")
            for a in range(i0, i1, BLOCK):
                for b in range(j0, j1, BLOCK):
                    rows, cols = slice(a, min(a + BLOCK, i1)), slice(b, min(b + BLOCK, j1))
                    if not land[rows, cols].any():
                        continue
                    fill = block(group, origin, latitude, altitude, capacity, rows, cols)[k0:k0 + n]
                    shape = (n, rows.stop - rows.start, cols.stop - cols.start)
                    pct = np.where(np.isnan(fill), FILL, np.round(100 * fill)).reshape(shape)
                    quarter[:, a - i0:rows.stop - i0, b - j0:cols.stop - j0] = pct.astype("uint8")
                    done += 1
            arr[:, i0:i1, j0:j1] = quarter
            log.info("%s %s : quart %d-%d x %d-%d, %d blocs, %.0f s", source, NAME, i0, i1, j0, j1,
                     done, time.time() - t0)
    verify(point, source, arr, origin, k0, land)
    arr.attrs["built"] = time.strftime("%Y-%m-%d %H:%M")
    size = sum(p.stat().st_size for p in (STORE / source / NAME).rglob("*") if p.is_file())
    log.info("%s %s : %d jours, %.2f Go, %.0f min", source, NAME, n, size / 1e9, (time.time() - t0) / 60)


def verify(point: zarr.Group, source: str, arr: zarr.Array, origin: date, k0: int, land: np.ndarray,
           samples: int = 20) -> None:
    """Land cells drawn at random, computed again one at a time with the
    functions of a place (soil.liquid, soil.balance): the same percent every day."""
    rng = np.random.default_rng(0)
    group, latitude = point[source], point["latitude"][:]
    altitude = np.nan_to_num(point["elevation"][:], nan=0.0)
    capacity = capacities(point)
    cells = np.argwhere(land)
    for i, j in cells[rng.choice(len(cells), samples, replace=False)]:
        rows, cols = slice(i, i + 1), slice(j, j + 1)
        v = {name: read(group, name, rows, cols)[:, 0] for name in INPUTS}
        n = len(v["tas"])
        days = np.datetime64(origin.isoformat()) + np.arange(n)
        doy = (days - days.astype("datetime64[Y]")).astype(int) + 1
        rs = v["rsds"] * et0.MJ_PER_W
        es, ea = et0.vapour(v["tasmax"], v["tasmin"], v["hurs"])
        rso = et0.clear_sky(et0.extraterrestrial(float(latitude[i]), doy), float(altitude[i, j]))
        rn = (1 - et0.ALBEDO) * rs - et0.net_longwave(v["tasmax"], v["tasmin"], ea, rs, rso)
        demand = et0.reference(v["tasmax"], v["tasmin"], ea, es, et0.wind_2m(v["sfcWind"]), rn,
                               et0.pressure(float(altitude[i, j])))
        fill = soil.balance(soil.liquid(v["tas"], v["pr"], origin), demand, float(capacity[i, j])).fill
        fill = fill[k0:k0 + arr.shape[0]]
        expected = np.where(np.isnan(fill), FILL, np.round(100 * fill)).astype("uint8")
        got = arr[:, i, j]
        if not np.array_equal(got, expected):
            bad = int((got != expected).sum())
            raise ValueError(f"{source} {NAME} : maille {i} {j}, {bad} jours differents du calcul d'un lieu")


def main(argv: list[str]) -> int:
    handler = logging.FileHandler(STORE.parent / "maps.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    point = zarr.open_group(POINT, mode="r")
    for source in argv or SOURCES:
        build(point, source)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
