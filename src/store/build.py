"""Serving store: corrected CORDEX rewritten as long series per point, in Zarr.

    python -m src.store.build cordex tasmax [tasmin ...]
    python -m src.store.build era5 tasmax [tasmin ...]

Run from the repo root, with the external drive plugged in. The yearly files
stay the reference: corrected CORDEX 1970-2100 (src.correction.qdm), daily
ERA5 1970-2005 (src.download.era5). The store is a copy that can be deleted
and rebuilt at any time. ERA5 is stored under the CORDEX names and units, and
masked to the CORDEX domain, so that a place has both or neither.

The yearly files hold whole maps, a year at a time: reading one point means
decompressing blocks of 122 days x 69 x 221 cells. The store turns them round:
one chunk holds 1970-2100 (47 847 days) for 2 x 2 cells, so any series at a
point, 3 months or 131 years, costs one chunk per variable. Chunks are packed
in shards of 20 x 20 cells, to keep the file count low (exFAT, object storage).

Values are stored as 16-bit integers, value = integer x step (0.01 in the
stored unit, 0.1 mm for precipitation: corrected pr reaches 1309 mm/day in
one cell, beyond 655.35), with a time delta filter and zstd. xarray decodes
them on reading (scale_factor, _FillValue). The rounding error is at most
step / 2.

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
from src.correction.qdm import ERA5_DAILY
from src.correction.qdm import OUT as CORRECTED
from src.correction.qdm import YEARS
from src.correction.remap import yearly

STORE = DATA / "serve" / "point.zarr"
CHUNK = 2   # cells per chunk, in latitude and longitude
SHARD = 20  # cells per shard, idem; also the height of a band


@dataclass(frozen=True)
class Var:
    units: str
    convert: Callable[[np.ndarray], np.ndarray]  # CORDEX units to stored units
    dtype: str  # int16 for signed values, uint16 for values >= 0
    step: float
    era5: str  # ERA5 field
    from_era5: Callable[[np.ndarray], np.ndarray]  # ERA5 units to stored units


def kelvin(x):
    return x - 273.15


def per_day(x):
    return x * 86400


def same(x):
    return x


def metres(x):
    return x * 1000


def percent(x):
    return x * 100


VARS = {
    "tasmax": Var("degC", kelvin, "int16", 0.01, "mx2t", kelvin),
    "tasmin": Var("degC", kelvin, "int16", 0.01, "mn2t", kelvin),
    "tas": Var("degC", kelvin, "int16", 0.01, "t2m", kelvin),
    "pr": Var("mm/day", per_day, "uint16", 0.1, "tp", metres),
    "clt": Var("%", same, "uint16", 0.01, "tcc", percent),
    "hurs": Var("%", same, "uint16", 0.01, "hurs", same),
    "sfcWind": Var("m/s", same, "uint16", 0.01, "si10", same),
}


@dataclass(frozen=True)
class Source:
    years: range
    path: Callable[[str, int], object]  # (variable, year) to the yearly file
    field: Callable[[str], str]  # variable to its name in the file
    convert: Callable[[str], Callable]  # variable to its conversion


SOURCES = {
    "cordex": Source(YEARS, lambda n, y: CORRECTED / yearly(n, y),
                     lambda n: n, lambda n: VARS[n].convert),
    "era5": Source(range(1970, 2006),
                   lambda n, y: ERA5_DAILY / f"{VARS[n].era5}_ERA5_day_{y}0101-{y}1231.nc",
                   lambda n: VARS[n].era5, lambda n: VARS[n].from_era5),
}

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("build")


def fill(dtype: str) -> int:
    return int(np.iinfo(dtype).min if dtype == "int16" else np.iinfo(dtype).max)


def domain() -> np.ndarray:
    """CORDEX domain on the grid: True where the corrected fields have values."""
    with xr.open_dataset(CORRECTED / yearly("tasmax", YEARS[0])) as ds:
        return np.isfinite(ds.tasmax[0].values)


def write_domain() -> None:
    """The CORDEX domain, (latitude, longitude), 1 inside: lets the server tell
    a covered place without reading a series."""
    with xr.open_dataset(CORRECTED / yearly("tasmax", YEARS[0])) as ds:
        lat, lon = ds.latitude.values, ds.longitude.values
    da = xr.DataArray(domain().astype("uint8"), dims=("latitude", "longitude"),
                      coords={"latitude": lat, "longitude": lon}, name="domain")
    da.to_dataset().to_zarr(STORE, mode="a", zarr_format=3, consolidated=False)


def grid(src: str, name: str) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]:
    """Days, latitudes and longitudes of the yearly files, checked year by year
    against each other and against the CORDEX grid."""
    s = SOURCES[src]
    days = pd.date_range(f"{s.years[0]}-01-01", f"{s.years[-1]}-12-31", freq="D")
    with xr.open_dataset(CORRECTED / yearly("tasmax", YEARS[0])) as ds:
        lat, lon = ds.latitude.values, ds.longitude.values
    for y in s.years:
        with xr.open_dataset(s.path(name, y)) as ds:
            if not ds.time.to_index().normalize().equals(days[days.year == y]):
                raise ValueError(f"{src} {name} {y} : jours manquants ou en trop")
            if not (np.array_equal(ds.latitude.values, lat) and np.array_equal(ds.longitude.values, lon)):
                raise ValueError(f"{src} {name} {y} : grille differente de CORDEX")
    return days, lat, lon


def create(src: str, name: str, days, lat, lon) -> zarr.Array:
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
        "scale_factor": v.step,
        "_FillValue": fill(v.dtype),
        "chunks": (len(days), CHUNK, CHUNK),
        "shards": (len(days), SHARD, SHARD),
        "filters": [Delta(dtype=v.dtype)],
        "compressors": [BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
    }}
    shutil.rmtree(STORE / src / name, ignore_errors=True)
    da.to_dataset().to_zarr(STORE, group=src, mode="a", encoding=encoding,
                            compute=False, zarr_format=3, consolidated=False)
    return zarr.open_array(STORE / src / name, mode="r+")


def band(src: str, name: str, i0: int, i1: int, inside: np.ndarray) -> np.ndarray:
    """Rows i0:i1 of every year, as stored integers (days, rows, longitudes);
    cells outside the CORDEX domain left empty."""
    s, v = SOURCES[src], VARS[name]
    xs = []
    for y in s.years:
        with netCDF4.Dataset(s.path(name, y)) as ds:
            var = ds[s.field(name)]
            var.set_auto_mask(False)
            xs.append(var[:, i0:i1, :])
    x = s.convert(name)(np.concatenate(xs))
    q = np.round(x / v.step)
    info = np.iinfo(v.dtype)
    ok = np.isfinite(q) & inside[i0:i1]
    # The fill value is reserved: the minimum of int16, the maximum of uint16.
    low, high = (info.min + 1, info.max) if v.dtype == "int16" else (info.min, info.max - 1)
    if (q[ok] < low).any() or (q[ok] > high).any():
        raise ValueError(f"{src} {name} lignes {i0}-{i1} : valeurs hors de la plage de {v.dtype} "
                         f"({np.nanmin(x):.2f} a {np.nanmax(x):.2f} {v.units})")
    return np.where(ok, q, fill(v.dtype)).astype(v.dtype)


def verify(src: str, name: str, inside: np.ndarray, n: int = 200) -> float:
    """Largest gap between the store, read through xarray, and the yearly
    files, over n random (point, year) pairs where the point has data."""
    s = SOURCES[src]
    rng = np.random.default_rng(0)
    store = xr.open_zarr(STORE, group=src, consolidated=False)[name]
    worst = 0.0
    for _ in range(n):
        y = int(rng.choice(s.years))
        with xr.open_dataset(s.path(name, y)) as ds:
            ref = ds[s.field(name)]
            i, j = rng.integers(ref.shape[1]), rng.integers(ref.shape[2])
            a = s.convert(name)(ref[:, i, j].values.astype("float64"))
        if not inside[i, j]:
            a[:] = np.nan
        b = store.sel(time=str(y))[:, i, j].values
        if not np.array_equal(np.isnan(a), np.isnan(b)):
            raise ValueError(f"{src} {name} {y} ({i}, {j}) : mailles vides differentes")
        if np.isfinite(a).any():
            worst = max(worst, float(np.nanmax(np.abs(a - b))))
    return worst


def build(src: str, name: str) -> None:
    t0 = time.time()
    step = VARS[name].step
    days, lat, lon = grid(src, name)
    inside = domain()
    arr = create(src, name, days, lat, lon)
    log.info("%s %s : %d jours, %d x %d mailles", src, name, len(days), len(lat), len(lon))
    for i0 in range(0, len(lat), SHARD):
        i1 = min(i0 + SHARD, len(lat))
        arr[:, i0:i1, :] = band(src, name, i0, i1, inside)
        log.info("%s %s : lignes %d-%d ecrites, %.0f s", src, name, i0, i1 - 1, time.time() - t0)
    size = sum(p.stat().st_size for p in (STORE / src / name).rglob("*") if p.is_file())
    worst = verify(src, name, inside)
    # Half a step, plus the float32 rounding of the source files (3e-5 K at 300 K).
    if worst > step / 2 + 1e-4:
        raise ValueError(f"{src} {name} : ecart maximal {worst:.4f}, au-dela de {step / 2}")
    arr.attrs["built"] = time.strftime("%Y-%m-%d %H:%M")
    log.info("%s %s : %.2f Go, ecart maximal au fichier source %.4f %s, %.0f min",
             src, name, size / 1e9, worst, VARS[name].units, (time.time() - t0) / 60)


def main(argv: list[str]) -> int:
    src, names = (argv[0], argv[1:]) if argv else (None, [])
    unknown = [n for n in names if n not in VARS]
    if src not in SOURCES or not names or unknown:
        print(f"Usage : python -m src.store.build {{{'|'.join(SOURCES)}}} <variables>\n"
              f"Variables possibles : {' '.join(VARS)}")
        return 1
    STORE.parent.mkdir(parents=True, exist_ok=True)
    write_domain()
    handler = logging.FileHandler(STORE.parent / "build.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    for name in names:
        try:
            build(src, name)
        except Exception:
            log.exception("%s %s : echec", src, name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
