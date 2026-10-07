"""Remap CORDEX daily fields onto the ERA5 0.25 deg grid.

    python -m src.correction.remap tas 1970-2100
    WSA_MODEL=mpi python -m src.correction.remap tas 1970-2100

Run from the repo root, with the external drive plugged in: CORDEX is read
from it and the remapped files are written to it, in cordex/eur11_025 (or the
folder of the run WSA_MODEL picks, src.correction.models), one file per year.

Each ERA5 cell takes the area-weighted mean of the CORDEX cells that overlap
it. Overlaps are measured by cutting every CORDEX cell into SUB x SUB
sub-cells, regular in the rotated grid, and dropping each sub-cell into the
ERA5 cell that holds its centre. At SUB = 20, the covered fraction of a full
ERA5 cell stays within 5 % of 1, worst near 18 E, where both grids line up.

ERA5 cells that CORDEX covers for less than MIN_COVER of their area, along the
edges of the rotated domain, are left missing.

The weights are computed once, for every variable, and kept in
data/correction/poids_eur11_era5.npz. They serve every run of
src.correction.models, all on the same grid. Days are stamped at 00h, as in ERA5,
where CORDEX stamps them at 12h.
"""

import logging
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import xarray as xr

from src.config import ARCHIVE, DATA
from src.correction.models import MODEL
from src.download.era5 import years_from

OUT = ARCHIVE / "cordex" / f"{MODEL.out}_025"
WEIGHTS = DATA / "correction" / "poids_eur11_era5.npz"
GRID = ARCHIVE / "era5" / "daily" / "t2m_ERA5_day_19700101-19701231.nc"

SUB = 20
MIN_COVER = 0.9

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("remap")


yearly = MODEL.yearly
source = MODEL.source


def target(name: str, year: int) -> Path:
    return OUT / yearly(name, year)


def to_geographic(rlat: np.ndarray, rlon: np.ndarray, plat: float, plon: float):
    """Rotated coordinates to latitude, longitude, all in degrees.

    Checked against the lat/lon stored in the CORDEX files: 1e-9 deg.
    """
    rp, rl = np.deg2rad(rlat), np.deg2rad(rlon)
    v = np.stack([np.cos(rp) * np.cos(rl), np.cos(rp) * np.sin(rl), np.sin(rp)])
    a, b = np.deg2rad(90 - plat), np.deg2rad(plon)
    rz = np.array([[np.cos(b), np.sin(b), 0], [-np.sin(b), np.cos(b), 0], [0, 0, 1]])
    ry = np.array([[np.cos(a), 0, -np.sin(a)], [0, 1, 0], [np.sin(a), 0, np.cos(a)]])
    flip = np.diag([-1.0, -1.0, 1.0])
    g = np.einsum("ji,j...->i...", flip @ ry @ rz, v)
    return np.rad2deg(np.arcsin(g[2])), np.rad2deg(np.arctan2(g[1], g[0]))


def build_weights() -> None:
    src = xr.open_dataset(source("tas", 1970))
    pole = src[src.tas.attrs["grid_mapping"]].attrs
    rlat, rlon = src.rlat.values, src.rlon.values
    grid = xr.open_dataset(GRID)
    lat, lon = grid.latitude.values, grid.longitude.values
    dlat, dlon = abs(lat[1] - lat[0]), lon[1] - lon[0]
    step = rlat[1] - rlat[0]

    rows, cols, areas = [], [], []
    ncol = np.arange(rlat.size * rlon.size).reshape(rlat.size, rlon.size)
    offsets = (np.arange(SUB) + 0.5) / SUB - 0.5
    for di in offsets:
        for dj in offsets:
            sp_lat, sp_lon = np.meshgrid(rlat + di * step, rlon + dj * step, indexing="ij")
            glat, glon = to_geographic(sp_lat, sp_lon, pole["grid_north_pole_latitude"],
                                       pole["grid_north_pole_longitude"])
            i = np.rint((lat[0] - glat) / dlat).astype(int)
            j = np.rint((glon - lon[0]) / dlon).astype(int)
            ok = (i >= 0) & (i < lat.size) & (j >= 0) & (j < lon.size)
            rows.append((i * lon.size + j)[ok])
            cols.append(ncol[ok])
            areas.append((np.cos(np.deg2rad(sp_lat)) * np.deg2rad(step / SUB) ** 2)[ok])
    w = sp.coo_matrix((np.concatenate(areas), (np.concatenate(rows), np.concatenate(cols))),
                      shape=(lat.size * lon.size, ncol.size)).tocsr()

    top = np.deg2rad(np.minimum(lat + dlat / 2, 90))
    bottom = np.deg2rad(lat - dlat / 2)
    cell = np.repeat((np.sin(top) - np.sin(bottom)) * np.deg2rad(dlon), lon.size)
    got = np.asarray(w.sum(axis=1)).ravel()
    cover = got / cell
    keep = cover >= MIN_COVER
    w = sp.diags(np.where(keep, 1 / np.where(got > 0, got, 1), 0)) @ w
    w.eliminate_zeros()

    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    np.savez(WEIGHTS, data=w.data.astype("float32"), indices=w.indices, indptr=w.indptr,
             shape=w.shape, cover=cover.reshape(lat.size, lon.size).astype("float32"))
    log.info("poids : %d mailles ERA5 gardees sur %d, couverture >= %.0f %%",
             keep.sum(), keep.size, 100 * MIN_COVER)


def load_weights() -> tuple[sp.csr_matrix, np.ndarray]:
    f = np.load(WEIGHTS)
    w = sp.csr_matrix((f["data"], f["indices"], f["indptr"]), shape=tuple(f["shape"]))
    return w, f["cover"] >= MIN_COVER


def remap(name: str, year: int, w: sp.csr_matrix, keep: np.ndarray,
          grid: xr.Dataset) -> xr.DataArray:
    src = xr.open_dataset(source(name, year)).sel(time=str(year))
    x = src[name].values.reshape(src.time.size, -1).T
    valid = ~np.isnan(x)
    if valid.all():
        y = w @ x
    else:
        # Missing CORDEX cells: average over the valid ones, if they hold enough weight.
        num = w @ np.where(valid, x, 0)
        den = w @ valid.astype("float32")
        y = np.where(den >= MIN_COVER, num / np.where(den > 0, den, 1), np.nan)
    y = y.T.reshape(src.time.size, *keep.shape).astype("float32")
    y[:, ~keep] = np.nan
    days = src.time.values.astype("datetime64[D]")
    da = xr.DataArray(y, name=name, dims=("time", "latitude", "longitude"),
                      coords={"time": np.array(days, dtype="datetime64[ns]"),
                              "latitude": grid.latitude, "longitude": grid.longitude})
    da.attrs = {k: v for k, v in src[name].attrs.items()
                if k in ("standard_name", "long_name", "units", "cell_methods")}
    da.attrs["remap"] = (f"area-weighted mean of CORDEX {MODEL.domain} cells onto the ERA5 0.25 deg "
                         f"grid, cells covered < {MIN_COVER:.0%} left missing")
    return da


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    name, ys = argv[0], years_from(argv[1:])
    if not WEIGHTS.exists():
        t0 = time.time()
        build_weights()
        log.info("poids calcules en %.0f s", time.time() - t0)
    w, keep = load_weights()
    grid = xr.open_dataset(GRID)
    OUT.mkdir(parents=True, exist_ok=True)
    for i, y in enumerate(ys, 1):
        out = target(name, y)
        if out.exists():
            continue
        t0 = time.time()
        part = out.with_suffix(".part")
        remap(name, y, w, keep, grid).to_netcdf(
            part, encoding={name: {"zlib": True, "complevel": 4}})
        part.rename(out)
        log.info("[%d/%d] %s %d en %.1f s", i, len(ys), name, y, time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
