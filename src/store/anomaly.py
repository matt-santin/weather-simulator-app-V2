"""Departure of the soil water from its normal, every day and every cell, for the map store.

    python -m src.store.anomaly

Read from the map store's `soil` (src.store.soil: percent of the available
water left at the end of the day), written beside it as `soil_anomaly`: the
day's percent minus the normal of its day of the year, in points of percent,
8-bit signed integers, FILL for no value. Negative: drier than usual.

The normal (decided 2026-11-16) is the same for the past and the simulation:
the mean of ERA5 1991-2020 for each day of the year, smoothed over 31 days
(15 on each side, across the turn of the year). A simulated year therefore
reads against today's climate. 29 February takes the normal of 28 February.

Computed a quarter of the domain at a time (the chunks of the map store), by
DAYS_AT_ONCE days. The attribute `built` is written last. Run again after
src.store.soil.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from datetime import date

import numpy as np
import zarr
from zarr.codecs import BloscCodec

from src.store.maps import DAYS, SOURCES, STORE

NAME = "soil_anomaly"
SOIL = "soil"
NORMAL_YEARS = (1991, 2020)
NORMAL_SOURCE = "era5"
HALF_WINDOW = 15  # days on each side of the day of the year
FILL = -128
DAYS_AT_ONCE = 4096

log = logging.getLogger("anomaly")
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler())


def slots(first: date, n: int) -> np.ndarray:
    """Day of the year of each of n days from ``first``, 0 to 364, 29 February on 28 February."""
    days = np.datetime64(first.isoformat()) + np.arange(n)
    month = days.astype("datetime64[M]").astype(int) % 12 + 1
    day = (days - days.astype("datetime64[M]")).astype(int) + 1
    of_year = (days - days.astype("datetime64[Y]")).astype(int)
    leap = ((days.astype("datetime64[Y]").astype(int) + 1970) % 4 == 0)  # 1970-2100: 2100 is not leap
    leap &= (days.astype("datetime64[Y]").astype(int) + 1970) != 2100
    after = leap & ((month > 2) | ((month == 2) & (day == 29)))
    return of_year - after


def normal(values: np.ndarray, first: date, fill: int, years: tuple[int, int] = NORMAL_YEARS,
           half: int = HALF_WINDOW) -> np.ndarray:
    """Mean of each day of the year over ``years``, smoothed over 2 x half + 1 days:
    365 x cells, NaN where a cell has no value. ``values``: days x cells, from ``first``."""
    n = values.shape[0]
    y = (np.datetime64(first.isoformat()) + np.arange(n)).astype("datetime64[Y]").astype(int) + 1970
    kept = np.nonzero((y >= years[0]) & (y <= years[1]))[0]
    slot = slots(first, n)[kept]
    total = np.zeros((365, values.shape[1]))
    count = np.zeros((365, values.shape[1]))
    for k0 in range(0, kept.size, DAYS_AT_ONCE):
        part = values[kept[k0:k0 + DAYS_AT_ONCE]]
        ok = part != fill
        np.add.at(total, slot[k0:k0 + DAYS_AT_ONCE], np.where(ok, part, 0).astype("float64"))
        np.add.at(count, slot[k0:k0 + DAYS_AT_ONCE], ok)
    with np.errstate(invalid="ignore"):
        daily = total / count
    wrapped = np.concatenate([daily[-half:], daily, daily[:half]])
    sums = np.cumsum(np.concatenate([np.zeros((1, daily.shape[1])), wrapped]), axis=0)
    width = 2 * half + 1
    return (sums[width:] - sums[:-width]) / width


def departure(values: np.ndarray, first: date, fill: int, base: np.ndarray) -> np.ndarray:
    """Each day minus the normal of its day of the year, rounded, int8, FILL without value."""
    out = np.round(values.astype("float64") - base[slots(first, values.shape[0])])
    out[(values == fill) | np.isnan(out)] = FILL
    return out.astype("int8")


def build() -> None:
    t0 = time.time()
    root = zarr.open_group(STORE, mode="a")
    reference = root[NORMAL_SOURCE][SOIL]
    ny, nx = reference.shape[1:]
    qy, qx = reference.chunks[1:]
    out = {}
    for source in SOURCES:
        soil = root[source][SOIL]
        if "built" not in soil.attrs:
            raise RuntimeError(f"{source} {SOIL} n'est pas termine : lancer python -m src.store.soil")
        shutil.rmtree(STORE / source / NAME, ignore_errors=True)
        arr = root[source].create_array(
            NAME, shape=soil.shape, dtype="int8", chunks=(DAYS, qy, qx), fill_value=FILL,
            compressors=[BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")])
        arr.attrs.update({"scale_factor": 1, "_FillValue": FILL, "units": "points", "start": soil.attrs["start"],
                          "normal": {"source": NORMAL_SOURCE, "years": list(NORMAL_YEARS),
                                     "window_days": 2 * HALF_WINDOW + 1}})
        for key in ("simulation", "reference", "capacity"):
            if key in soil.attrs:
                arr.attrs[key] = soil.attrs[key]
        out[source] = arr
    first_ref = date.fromisoformat(reference.attrs["start"])
    for i0 in range(0, ny, qy):
        for j0 in range(0, nx, qx):
            i1, j1 = min(i0 + qy, ny), min(j0 + qx, nx)
            shape = (i1 - i0, j1 - j0)
            base = normal(reference[:, i0:i1, j0:j1].reshape(reference.shape[0], -1), first_ref,
                          reference.attrs["_FillValue"])
            for source, arr in out.items():
                soil = root[source][SOIL]
                first = date.fromisoformat(soil.attrs["start"])
                for k0 in range(0, soil.shape[0], DAYS_AT_ONCE):
                    k1 = min(k0 + DAYS_AT_ONCE, soil.shape[0])
                    part = soil[k0:k1, i0:i1, j0:j1].reshape(k1 - k0, -1)
                    day = date.fromordinal(first.toordinal() + k0)
                    arr[k0:k1, i0:i1, j0:j1] = departure(part, day, soil.attrs["_FillValue"], base).reshape(
                        k1 - k0, *shape)
            log.info("%s : quart %d-%d x %d-%d, %.0f s", NAME, i0, i1, j0, j1, time.time() - t0)
    for source, arr in out.items():
        arr.attrs["built"] = time.strftime("%Y-%m-%d %H:%M")
        size = sum(p.stat().st_size for p in (STORE / source / NAME).rglob("*") if p.is_file())
        log.info("%s %s : %d jours, %.2f Go", source, NAME, arr.shape[0], size / 1e9)
    log.info("%s : %.0f min", NAME, (time.time() - t0) / 60)


def main(argv: list[str]) -> int:
    handler = logging.FileHandler(STORE.parent / "maps.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
