"""Map store: the serving store turned round, a few days over the whole domain.

    python -m src.store.maps tasmax

The point store (src.store.build) holds 1970-2100 for 2 x 2 cells per chunk:
right for a series at a place, wrong for a map, which would read every chunk
of the domain. This store holds DAYS days over a quarter of the domain per
chunk, so a season of 92 days costs 4 x 4 chunks.

It is copied from point.zarr, raw integers to raw integers (same step, same
fill value): no rounding is added, and the verification checks equality.
Groups and periods are the site's: era5 1970-2025, cordex 2027-2100, 0.25 deg.

At the root: latitude, longitude, and land (1 where the ERA5 land-sea mask is
at least 0.5 and CORDEX covers the cell). The mask is read once from the
external drive; the store then serves without it.

Each group is read a quarter of the domain at a time (about 1.2 GB for
cordex). The attribute `built` is written last: an array without it is
incomplete.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from datetime import date

import numpy as np
import xarray as xr
import zarr
from zarr.codecs import BloscCodec

from src.config import ARCHIVE, DATA
from src.store.build import STORE as POINT

STORE = DATA / "serve" / "map.zarr"
DAYS = 32  # days per chunk
SOURCES = {"era5": (date(1970, 1, 1), date(2025, 12, 31)), "cordex": (date(2027, 1, 1), date(2100, 12, 31))}
EPOCH = date(1970, 1, 1)

log = logging.getLogger("maps")
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler())


def write_grid(point: zarr.Group) -> tuple[int, int]:
    lat, lon = point["latitude"][:], point["longitude"][:]
    domain = point["domain"][:].astype(bool)
    lsm = xr.open_dataarray(ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc")
    lsm = lsm.sel(latitude=xr.DataArray(lat, dims="y"), longitude=xr.DataArray(lon, dims="x"))
    if not (np.array_equal(lsm.latitude.values, lat) and np.array_equal(lsm.longitude.values, lon)):
        raise ValueError("masque terre-mer : grille differente du stockage")
    land = (lsm.values >= 0.5) & domain
    root = zarr.open_group(STORE, mode="a", zarr_format=3)
    root.create_array("latitude", data=lat, overwrite=True)
    root.create_array("longitude", data=lon, overwrite=True)
    root.create_array("land", data=land.astype("uint8"), overwrite=True)
    log.info("grille : %d x %d mailles, %d terrestres", lat.size, lon.size, land.sum())
    return lat.size, lon.size


def build(point: zarr.Group, source: str, name: str, ny: int, nx: int) -> None:
    t0 = time.time()
    first, last = SOURCES[source]
    src = point[source][name]
    k0 = (first - EPOCH).days - int(point[source]["time"][0])
    n = (last - first).days + 1
    qy, qx = (ny + 1) // 2, (nx + 1) // 2
    shutil.rmtree(STORE / source / name, ignore_errors=True)
    group = zarr.open_group(STORE, mode="a").require_group(source)
    arr = group.create_array(
        name, shape=(n, ny, nx), dtype=src.dtype, chunks=(DAYS, qy, qx),
        fill_value=src.attrs["_FillValue"],
        compressors=[BloscCodec(cname="zstd", clevel=5, shuffle="shuffle")],
    )
    arr.attrs.update({
        "scale_factor": src.attrs["scale_factor"],
        "_FillValue": src.attrs["_FillValue"],
        "units": src.attrs.get("units", "degC"),
        "start": first.isoformat(),
    })
    for i0 in range(0, ny, qy):
        for j0 in range(0, nx, qx):
            i1, j1 = min(i0 + qy, ny), min(j0 + qx, nx)
            arr[:, i0:i1, j0:j1] = src[k0:k0 + n, i0:i1, j0:j1]
            log.info("%s %s : quart %d-%d x %d-%d, %.0f s", source, name, i0, i1, j0, j1, time.time() - t0)
    verify(src, arr, k0)
    arr.attrs["built"] = time.strftime("%Y-%m-%d %H:%M")
    size = sum(p.stat().st_size for p in (STORE / source / name).rglob("*") if p.is_file())
    log.info("%s %s : %d jours, %.2f Go, %.0f min", source, name, n, size / 1e9, (time.time() - t0) / 60)


def verify(src: zarr.Array, arr: zarr.Array, k0: int, samples: int = 200) -> None:
    """Random days and cells must hold the same integers in both stores."""
    rng = np.random.default_rng(0)
    for _ in range(samples):
        k = int(rng.integers(arr.shape[0]))
        i, j = int(rng.integers(arr.shape[1])), int(rng.integers(arr.shape[2]))
        if arr[k, i, j] != src[k0 + k, i, j]:
            raise ValueError(f"ecart au jour {k}, maille {i} {j}")


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage : python -m src.store.maps <variables>, par exemple tasmax")
        return 1
    STORE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(STORE.parent / "maps.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    point = zarr.open_group(POINT, mode="r")
    ny, nx = write_grid(point)
    for name in argv:
        for source in SOURCES:
            build(point, source, name, ny, nx)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
