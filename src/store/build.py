"""Serving store: corrected CORDEX rewritten as long series per point, in Zarr.

    python -m src.store.build tasmax [tasmin ...]

Run from the repo root, with the external drive plugged in. The corrected
yearly files (src.correction.qdm) stay the reference; the store is a copy that
can be deleted and rebuilt at any time.

The yearly files hold whole maps, a year at a time: reading one point means
decompressing blocks of 122 days x 69 x 221 cells. The store turns them round:
one chunk holds 1970-2100 (47 847 days) for 2 x 2 cells, so any series at a
point, 3 months or 131 years, costs one chunk per variable. Chunks are packed
in shards of 20 x 20 cells, to keep the file count low (exFAT, object storage).

Values are stored as 16-bit integers, value = integer x STEP (0.01 in the
stored unit), with a time delta filter and zstd. xarray decodes them on
reading (scale_factor, _FillValue). The rounding error is at most STEP / 2.

The store is built one band of 20 latitudes (one row of shards) at a time:
about 1.7 GB of memory, 50 s of reading from the drive per band. The attribute
`built` is written last: an array without it is incomplete.
"""

import logging
import shutil
import sys
import time
from dataclasses import dataclass
from typing import Callable

import dask.array
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
import zarr
from zarr.codecs import BloscCodec
from zarr.codecs.numcodecs import Delta

from src.config import DATA
from src.correction.qdm import OUT as CORRECTED
from src.correction.qdm import YEARS
from src.correction.remap import yearly

STORE = DATA / "serve" / "point.zarr"
GROUP = "cordex"
STEP = 0.01
CHUNK = 2   # cells per chunk, in latitude and longitude
SHARD = 20  # cells per shard, idem; also the height of a band


@dataclass(frozen=True)
class Var:
    units: str
    convert: Callable[[np.ndarray], np.ndarray]  # CORDEX units to stored units
    dtype: str  # int16 for signed values, uint16 for values >= 0


def kelvin(x):
    return x - 273.15


def per_day(x):
    return x * 86400


def same(x):
    return x


VARS = {
    "tasmax": Var("degC", kelvin, "int16"),
    "tasmin": Var("degC", kelvin, "int16"),
    "tas": Var("degC", kelvin, "int16"),
    "pr": Var("mm/day", per_day, "uint16"),
    "clt": Var("%", same, "uint16"),
    "hurs": Var("%", same, "uint16"),
}

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("build")


def fill(dtype: str) -> int:
    return int(np.iinfo(dtype).min if dtype == "int16" else np.iinfo(dtype).max)


def grid(name: str) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """Days, latitudes and longitudes of the corrected files, checked year by year."""
    days = pd.date_range(f"{YEARS[0]}-01-01", f"{YEARS[-1]}-12-31", freq="D")
    first = xr.open_dataset(CORRECTED / yearly(name, YEARS[0]))
    lat, lon = first.latitude.values, first.longitude.values
    for y in YEARS:
        with xr.open_dataset(CORRECTED / yearly(name, y)) as ds:
            if not ds.time.to_index().normalize().equals(days[days.year == y]):
                raise ValueError(f"{name} {y} : jours manquants ou en trop")
            if not (np.array_equal(ds.latitude.values, lat) and np.array_equal(ds.longitude.values, lon)):
                raise ValueError(f"{name} {y} : grille differente de {YEARS[0]}")
    return days, lat, lon


def create(name: str, days, lat, lon) -> zarr.Array:
    """Empty array with its coordinates and CF attributes, written by xarray so
    that xarray decodes it; the values are then written raw, band by band."""
    v = VARS[name]
    shape = (len(days), len(lat), len(lon))
    empty = dask.array.zeros(shape, dtype="float32", chunks=(len(days), SHARD, len(lon)))
    da = xr.DataArray(empty, dims=("time", "latitude", "longitude"),
                      coords={"time": days, "latitude": lat, "longitude": lon},
                      name=name, attrs={"units": v.units})
    encoding = {name: {
        "dtype": v.dtype,
        "scale_factor": STEP,
        "_FillValue": fill(v.dtype),
        "chunks": (len(days), CHUNK, CHUNK),
        "shards": (len(days), SHARD, SHARD),
        "filters": [Delta(dtype=v.dtype)],
        "compressors": [BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
    }}
    shutil.rmtree(STORE / GROUP / name, ignore_errors=True)
    da.to_dataset().to_zarr(STORE, group=GROUP, mode="a", encoding=encoding,
                            compute=False, zarr_format=3, consolidated=False)
    return zarr.open_array(STORE / GROUP / name, mode="r+")


def band(name: str, i0: int, i1: int) -> np.ndarray:
    """Rows i0:i1 of every year, as stored integers (days, rows, longitudes)."""
    v = VARS[name]
    xs = []
    for y in YEARS:
        with netCDF4.Dataset(CORRECTED / yearly(name, y)) as ds:
            var = ds[name]
            var.set_auto_mask(False)
            xs.append(var[:, i0:i1, :])
    x = v.convert(np.concatenate(xs))
    q = np.round(x / STEP)
    info = np.iinfo(v.dtype)
    ok = np.isfinite(q)
    if (q[ok] < info.min + 1).any() or (q[ok] > info.max - 1).any():
        raise ValueError(f"{name} lignes {i0}-{i1} : valeurs hors de la plage de {v.dtype} "
                         f"({np.nanmin(x):.2f} a {np.nanmax(x):.2f} {v.units})")
    return np.where(ok, q, fill(v.dtype)).astype(v.dtype)


def verify(name: str, n: int = 200) -> float:
    """Largest gap between the store, read through xarray, and the corrected
    files, over n random (point, year) pairs where the point has data."""
    rng = np.random.default_rng(0)
    store = xr.open_zarr(STORE, group=GROUP, consolidated=False)[name]
    worst = 0.0
    for _ in range(n):
        y = int(rng.choice(YEARS))
        with xr.open_dataset(CORRECTED / yearly(name, y)) as ds:
            ref = ds[name]
            i, j = rng.integers(ref.shape[1]), rng.integers(ref.shape[2])
            a = VARS[name].convert(ref[:, i, j].values)
        b = store.sel(time=str(y))[:, i, j].values
        if not np.array_equal(np.isnan(a), np.isnan(b)):
            raise ValueError(f"{name} {y} ({i}, {j}) : mailles vides differentes")
        if np.isfinite(a).any():
            worst = max(worst, float(np.nanmax(np.abs(a - b))))
    return worst


def build(name: str) -> None:
    t0 = time.time()
    days, lat, lon = grid(name)
    arr = create(name, days, lat, lon)
    log.info("%s : %d jours, %d x %d mailles", name, len(days), len(lat), len(lon))
    for i0 in range(0, len(lat), SHARD):
        i1 = min(i0 + SHARD, len(lat))
        arr[:, i0:i1, :] = band(name, i0, i1)
        log.info("%s : lignes %d-%d ecrites, %.0f s", name, i0, i1 - 1, time.time() - t0)
    size = sum(p.stat().st_size for p in (STORE / GROUP / name).rglob("*") if p.is_file())
    worst = verify(name)
    if worst > STEP / 2 * 1.001:
        raise ValueError(f"{name} : ecart maximal {worst:.4f}, au-dela de {STEP / 2}")
    arr.attrs["built"] = time.strftime("%Y-%m-%d %H:%M")
    log.info("%s : %.2f Go, ecart maximal au fichier corrige %.4f %s, %.0f min",
             name, size / 1e9, worst, VARS[name].units, (time.time() - t0) / 60)


def main(argv: list[str]) -> int:
    names = argv or []
    unknown = [n for n in names if n not in VARS]
    if not names or unknown:
        print(f"Variables possibles : {' '.join(VARS)}")
        return 1
    STORE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(STORE.parent / "build.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    for name in names:
        build(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
