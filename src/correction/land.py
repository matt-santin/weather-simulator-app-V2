"""Temperatures and humidity at 0.1 deg: CORDEX corrected against ERA5-Land.

    python -m src.correction.land remap tasmax 1970-2100
    python -m src.correction.land qdm tasmax
    python -m src.correction.land swap          tasmin > tasmax days, once both are done
    WSA_MODEL=mpi python -m src.correction.land ...   (src.correction.models)

Run from the repo root, with the external drive plugged in. The 0.25 deg chain
(src.correction.remap, qdm, derive) is left as it is: this one runs beside it,
for tas, tasmax and tasmin only, against ERA5-Land (src.download.era5land),
whose 2 m fields are brought down to a finer relief. hurs was corrected this
way too and not retained (docs/correction.md, section 9): it stays at 0.25 deg.

remap: CORDEX EUR-11 (0.11 deg, rotated pole) onto the ERA5-Land grid (0.1 deg),
by the area-weighted mean of remap.py, sub-cells included (SUB = 20). A 0.1 deg
cell takes one or two CORDEX cells, so the native detail is kept. Cells covered
under MIN_COVER, and sea cells (no ERA5-Land value), are left missing. The
remapped files (REMAPPED) serve qdm and the split sample of land_check, and
nothing after: they were deleted once checked, and remap rebuilds them in
about 30 min per variable.

qdm: the method of qdm.py, unchanged (same functions): calibration on
1970-2005, per cell and calendar month, 100 quantiles, 30-year sliding window,
additive. References:

    tas     t2m     daily mean of hourly t2m
    tasmax  t2mmax  daily maximum of hourly t2m (ERA5 mx2t is the maximum over
                    the model time step, a little higher: the corrected Tx is
                    therefore a little lower than at 0.25 deg)
    tasmin  t2mmin  daily minimum of hourly t2m

About 295 000 land cells, against 53 500 at 0.25 deg: the cells are cut into
batches of BATCH, each with its own memmap on the Mac (about 56 GB in all,
deleted at the end), so that one month of one batch, all years, fits in memory.

swap: tasmax and tasmin are corrected apart; where tasmin > tasmax, the two are
exchanged, as derive.py does at 0.25 deg.
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
from src.correction.qdm import CAL, LEVELS, NQ, VARS as VARS_025, WINDOW, YEARS, Var, calibrate, correct, window
from src.correction.remap import MIN_COVER, SUB, source, to_geographic, yearly
from src.download.era5 import years_from

LAND = ARCHIVE / "era5land" / "daily"
GRID = LAND / "t2m_ERA5-Land_day_19700101-19701231.nc"
WEIGHTS = DATA / "correction" / "poids_eur11_era5land.npz"
REMAPPED = ARCHIVE / "cordex" / f"{MODEL.out}_010"
OUT = ARCHIVE / "cordex" / f"{MODEL.out}_010_qdm"
WORK = DATA / "correction" / MODEL.tables / "land"
BATCH = 40_000

REFERENCE = {"tas": "t2m", "tasmax": "t2mmax", "tasmin": "t2mmin"}
VARS: dict[str, Var] = {n: VARS_025[n] for n in REFERENCE}

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("land")


def land_file(field: str, year: int) -> Path:
    return LAND / f"{field}_ERA5-Land_day_{year}0101-{year}1231.nc"


# --- remap -------------------------------------------------------------------


def build_weights() -> None:
    """remap.build_weights, onto the ERA5-Land grid; sea cells dropped."""
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
    land = np.isfinite(grid.t2m.isel(time=0).values).ravel()
    keep = (cover >= MIN_COVER) & land
    w = sp.diags(np.where(keep, 1 / np.where(got > 0, got, 1), 0)) @ w
    w.eliminate_zeros()

    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    np.savez(WEIGHTS, data=w.data.astype("float32"), indices=w.indices, indptr=w.indptr,
             shape=w.shape, keep=keep.reshape(lat.size, lon.size))
    log.info("poids : %d mailles ERA5-Land gardees sur %d (terre, couverture >= %.0f %%)",
             keep.sum(), keep.size, 100 * MIN_COVER)


def load_weights() -> tuple[sp.csr_matrix, np.ndarray]:
    f = np.load(WEIGHTS)
    w = sp.csr_matrix((f["data"], f["indices"], f["indptr"]), shape=tuple(f["shape"]))
    return w, f["keep"]


def remapped(name: str, year: int) -> Path:
    return REMAPPED / yearly(name, year)


def remap_year(name: str, year: int, w: sp.csr_matrix, keep: np.ndarray,
               grid: xr.Dataset) -> xr.DataArray:
    src = xr.open_dataset(source(name, year)).sel(time=str(year))
    x = src[name].values.reshape(src.time.size, -1).T
    valid = ~np.isnan(x)
    if valid.all():
        y = w @ x
    else:
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
    da.attrs["remap"] = (f"area-weighted mean of CORDEX {MODEL.domain} cells onto the ERA5-Land "
                         f"0.1 deg grid, land only, cells covered < {MIN_COVER:.0%} left missing")
    return da


def remap(name: str, years: list[int]) -> None:
    if not WEIGHTS.exists():
        t0 = time.time()
        build_weights()
        log.info("poids calcules en %.0f s", time.time() - t0)
    w, keep = load_weights()
    grid = xr.open_dataset(GRID)
    REMAPPED.mkdir(parents=True, exist_ok=True)
    for i, y in enumerate(years, 1):
        out = remapped(name, y)
        if out.exists():
            continue
        t0 = time.time()
        part = out.with_suffix(".part")
        remap_year(name, y, w, keep, grid).to_netcdf(
            part, encoding={name: {"zlib": True, "complevel": 4}})
        part.rename(out)
        log.info("[%d/%d] %s %d en %.1f s", i, len(years), name, y, time.time() - t0)


# --- qdm ---------------------------------------------------------------------


def qdm(name: str) -> None:
    v = VARS[name]
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    batches = [cells[a:a + BATCH] for a in range(0, cells.size, BATCH)]
    for y in YEARS:
        if not remapped(name, y).exists():
            raise FileNotFoundError(f"{remapped(name, y)} absent : lancer remap d'abord")
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    days = np.concatenate([np.arange(f"{y}-01-01", f"{y + 1}-01-01", dtype="datetime64[D]")
                           for y in YEARS])
    year = days.astype("datetime64[Y]").astype(int) + 1970
    month = days.astype("datetime64[M]").astype(int) % 12 + 1
    in_cal = (year >= CAL[0]) & (year <= CAL[1])
    ref_days = days[in_cal]
    ref_month = month[in_cal]

    # Model and reference, (days, cells of the batch), one memmap per batch.
    def pack(kind: str, b: int, n: int) -> np.memmap:
        return np.lib.format.open_memmap(WORK / f"_{kind}_{name}_{b:02d}.tmp", mode="w+",
                                         dtype="float32", shape=(n, batches[b].size))

    series = [pack("cordex", b, days.size) for b in range(len(batches))]
    refs = [pack("ref", b, ref_days.size) for b in range(len(batches))]
    t0 = time.time()
    for y in YEARS:
        x = xr.open_dataset(remapped(name, y))[name].values.reshape(-1, keep.size)
        for b, cb in enumerate(batches):
            series[b][year == y] = x[:, cb]
    log.info("CORDEX lu en %.0f s, %d mailles en %d paquets", time.time() - t0,
             cells.size, len(batches))
    t0 = time.time()
    ref_year = year[in_cal]
    for y in range(CAL[0], CAL[1] + 1):
        x = xr.open_dataset(land_file(REFERENCE[name], y))[REFERENCE[name]].values
        x = v.convert(x.reshape(x.shape[0], -1))
        for b, cb in enumerate(batches):
            refs[b][ref_year == y] = x[:, cb]
    log.info("ERA5-Land lu en %.0f s", time.time() - t0)

    tables = {k: np.full((12, NQ, cells.size), np.nan, "float32") for k in ("ref", "hist")}
    for b, cb in enumerate(batches):
        t0 = time.time()
        at = slice(b * BATCH, b * BATCH + cb.size)
        for m in range(1, 13):
            rows = np.flatnonzero(month == m)
            raw = np.asarray(series[b][rows])
            cal = calibrate(np.asarray(refs[b][ref_month == m]), raw[in_cal[rows]], v)
            tables["ref"][m - 1, :, at] = cal["ref"]
            tables["hist"][m - 1, :, at] = cal["hist"]
            yr = year[rows]
            x = np.empty_like(raw)
            for y in YEARS:
                lo, hi = window(y)
                now = yr == y
                x[now] = correct(raw[now], raw[(yr >= lo) & (yr <= hi)], cal, v)
            series[b][rows] = x
        series[b].flush()
        log.info("paquet %d/%d corrige en %.0f s", b + 1, len(batches), time.time() - t0)

    grid = xr.open_dataset(GRID)
    xr.Dataset(
        {k: (("month", "quantile", "cell"), a) for k, a in tables.items()},
        coords={"month": np.arange(1, 13), "quantile": LEVELS, "cell": cells},
        attrs={"ref": f"ERA5-Land {REFERENCE[name]}, in CORDEX units",
               "hist": f"CORDEX {name} remapped to 0.1 deg", "kind": v.kind,
               "period": f"{CAL[0]}-{CAL[1]}", "grid": "ERA5-Land 0.1 deg, land",
               "cell": "flat index into (latitude, longitude)",
               "latitude": grid.latitude.values, "longitude": grid.longitude.values},
    ).to_netcdf(WORK / f"{name}_quantiles_{CAL[0]}-{CAL[1]}.nc")

    for y in YEARS:
        src = xr.open_dataset(remapped(name, y))[name]
        out = np.full((src.time.size, keep.size), np.nan, "float32")
        for b, cb in enumerate(batches):
            out[:, cb] = series[b][year == y]
        da = src.copy(data=out.reshape(src.shape))
        da.attrs["bias_correction"] = (
            f"QDM additive (Cannon 2015) against ERA5-Land {REFERENCE[name]}, "
            f"{CAL[0]}-{CAL[1]}, per calendar month, {NQ} quantiles, {WINDOW}-year sliding window"
            + (f", clipped to {v.bounds}" if v.bounds != (None, None) else ""))
        path = OUT / yearly(name, y)
        part = path.with_suffix(".part")
        da.to_netcdf(part, encoding={name: {"zlib": True, "complevel": 4}})
        part.rename(path)
    for arr in series + refs:
        path = Path(arr.filename)
        del arr
        path.unlink()
    log.info("%s corrige, fichiers dans %s", name, OUT)


# --- swap --------------------------------------------------------------------


def swap() -> None:
    """Days with tasmin > tasmax: the two exchanged, in place. Running it again changes nothing."""
    total = 0
    for y in YEARS:
        hi = xr.open_dataarray(OUT / yearly("tasmax", y)).load()
        lo = xr.open_dataarray(OUT / yearly("tasmin", y)).load()
        bad = (lo > hi).values
        n = int(bad.sum())
        if n:
            h, low = hi.values.copy(), lo.values.copy()
            hi.values[bad], lo.values[bad] = low[bad], h[bad]
            for da in (hi, lo):
                path = OUT / yearly(da.name, y)
                part = path.with_suffix(".part")
                da.to_netcdf(part, encoding={da.name: {"zlib": True, "complevel": 4}})
                part.rename(path)
        total += n
    log.info("tn_tx : %d valeurs echangees sur 1970-2100", total)


def main(argv: list[str]) -> int:
    if argv[:1] == ["swap"]:
        swap()
        return 0
    if len(argv) >= 2 and argv[0] in ("remap", "qdm") and argv[1] in VARS:
        if argv[0] == "remap":
            remap(argv[1], years_from(argv[2:]) if argv[2:] else list(YEARS))
        else:
            qdm(argv[1])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
