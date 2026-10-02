"""Pull ERA5-Land 2 m temperature and dew point from Earth Data Hub, as daily values.

    python -m src.download.era5land 1970-2024

Run from the repo root. Needs the Earth Data Hub API key in ~/.edhrc.

ERA5-Land runs at 0.1 deg over land only (sea cells are missing), with the
2 m temperature brought down to its finer orography. It serves no daily
extremes and no relative humidity: both are computed here from the hourly
fields, which are never stored.

    t2m      daily mean of hourly t2m, K
    t2mmax   daily maximum of hourly t2m, K (ERA5 mx2t is the maximum over the
             model time step, slightly higher)
    t2mmin   daily minimum of hourly t2m, K
    d2m      daily mean of hourly d2m, K
    hurs     daily mean of hourly relative humidity over water, %, from t2m
             and d2m with the IFS saturation pressure, as for ERA5

Days are UTC days, 00h to 23h: both fields are instantaneous, nothing is shifted.

**Read by native chunk, so that each chunk is billed once.** Earth Data Hub
counts every chunk read, 500 000 a month. A chunk is 120 days x 64 x 64 cells
(6.4 deg), the EUR-11 box covers 9 x 19 of them, and the chunks start at
1950-01-01 00h, so a chunk holds 120 whole days. One chunk of time is read at a
time, one row of 64 latitudes at a time (about 1.6 GB in memory), and its daily
values are written to data/era5land/_blocs/. Yearly files are then assembled
from the blocks, and a block is deleted once no requested year needs it.
Reading year by year instead would read the chunks on each new year twice:
about 37 000 reads per variable for 1970-2024, against about 29 000.

Anything already on disk (or archived) is skipped, so the run is resumable.
"""

import logging
import sys
import time
from pathlib import Path

import dask
import numpy as np
import pandas as pd
import xarray as xr

from src.config import ERA5LAND, held
from src.download.era5 import HUB, years_from

LAND = "reanalysis-era5-land-no-antartica-v0.zarr"
OUT = ERA5LAND / "daily"
BLOCKS = ERA5LAND / "_blocs"  # "_": left on the Mac by src.archive

# The smallest 0.1 deg box around the 0.25 deg EUR-11 box of ERA5.
NORTH, WEST, SOUTH, EAST = 73.0, -45.0, 21.7, 65.3
STEP = 0.1
EPS = STEP / 10  # the coordinates carry float noise (0.09999999999999432)
CHUNK_HOURS = 2880
CHUNK_CELLS = 64
FIELDS = ("t2m", "t2mmax", "t2mmin", "d2m", "hurs")
ATTRS = {
    "t2m": ("K", "2 m temperature, daily mean of hourly values"),
    "t2mmax": ("K", "2 m temperature, daily maximum of hourly values"),
    "t2mmin": ("K", "2 m temperature, daily minimum of hourly values"),
    "d2m": ("K", "2 m dew point temperature, daily mean of hourly values"),
    "hurs": ("%", "2 m relative humidity over water, daily mean of hourly values"),
}

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("era5land")


def saturation(t: np.ndarray) -> np.ndarray:
    # Saturation vapour pressure over water, in Pa, Tetens form used by the IFS (as era5.py).
    return 611.21 * np.exp(17.502 * (t - 273.16) / (t - 32.19))


def target(name: str, year: int) -> Path:
    return OUT / f"{name}_ERA5-Land_day_{year}0101-{year}1231.nc"


def block_path(k: int) -> Path:
    return BLOCKS / f"bloc_{k:04d}.nc"


class Land:
    """The hourly dataset and the indices of the EUR-11 box in it."""

    def __init__(self, url: str) -> None:
        self.ds = xr.open_dataset(url + LAND, engine="zarr", chunks={})
        lat = self.ds.latitude.values
        lon = self.ds.longitude.values
        self.rows = np.where((lat <= NORTH + EPS) & (lat >= SOUTH - EPS))[0]
        self.west = np.where(lon >= 360 + WEST - EPS)[0]
        self.east = np.where(lon <= EAST + EPS)[0]
        self.latitude = np.round(lat[self.rows], 2)
        self.longitude = np.round(np.concatenate([lon[self.west] - 360, lon[self.east]]), 2)
        self.start = pd.Timestamp(self.ds.valid_time.values[0])
        if self.start != pd.Timestamp("1950-01-01T00"):
            raise RuntimeError(f"le jeu commence le {self.start}, les blocs ne sont plus alignes")
        self.end = pd.Timestamp(self.ds.valid_time.values[-1])

    def chunk_of(self, day: pd.Timestamp) -> int:
        return int((day - self.start) / pd.Timedelta(hours=1)) // CHUNK_HOURS

    def days_of(self, k: int) -> pd.DatetimeIndex:
        first = self.start + pd.Timedelta(hours=k * CHUNK_HOURS)
        return pd.date_range(first, periods=CHUNK_HOURS // 24, freq="D")

    def read(self, k: int) -> dict[str, np.ndarray]:
        """Daily fields of time chunk k over the box, (days, latitude, longitude)."""
        hours = slice(k * CHUNK_HOURS, (k + 1) * CHUNK_HOURS)
        n_days = CHUNK_HOURS // 24
        shape = (n_days, len(self.rows), len(self.longitude))
        out = {f: np.full(shape, np.nan, dtype="float32") for f in FIELDS}
        # One row of native chunks at a time: every chunk is read once.
        west = slice(self.west[0], self.west[-1] + 1)
        east = slice(self.east[0], self.east[-1] + 1)
        for r in np.unique(self.rows // CHUNK_CELLS):
            sel = np.where(self.rows // CHUNK_CELLS == r)[0]
            rows = slice(self.rows[sel[0]], self.rows[sel[-1]] + 1)
            parts = []
            for v in ("t2m", "d2m"):
                da = self.ds[v].isel(valid_time=hours, latitude=rows)
                parts.append(xr.concat([da.isel(longitude=west), da.isel(longitude=east)],
                                       dim="longitude"))
            t, d = (p.values for p in dask.compute(*parts))
            t = t.reshape(n_days, 24, len(sel), -1)
            d = d.reshape(n_days, 24, len(sel), -1)
            band = slice(sel[0], sel[-1] + 1)
            out["t2m"][:, band] = t.mean(axis=1)
            out["t2mmax"][:, band] = t.max(axis=1)
            out["t2mmin"][:, band] = t.min(axis=1)
            out["d2m"][:, band] = d.mean(axis=1)
            for a in range(0, n_days, 20):  # by 20 days, to bound the temporaries
                b = min(a + 20, n_days)
                rh = 100 * saturation(d[a:b]) / saturation(t[a:b])
                out["hurs"][a:b, band] = np.minimum(rh, 100).mean(axis=1)
        return out

    def write_block(self, k: int, fields: dict[str, np.ndarray]) -> None:
        coords = {"time": self.days_of(k), "latitude": self.latitude, "longitude": self.longitude}
        ds = xr.Dataset({f: (("time", "latitude", "longitude"), a) for f, a in fields.items()},
                        coords=coords)
        BLOCKS.mkdir(parents=True, exist_ok=True)
        out = block_path(k)
        part = out.with_suffix(".part")
        ds.to_netcdf(part, encoding={f: {"zlib": True, "complevel": 1} for f in fields})
        part.rename(out)


def assemble(land: Land, year: int) -> None:
    """The yearly files of one year, from the blocks that cover it."""
    days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    ks = range(land.chunk_of(days[0]), land.chunk_of(days[-1]) + 1)
    ds = xr.concat([xr.open_dataset(block_path(k)) for k in ks], dim="time").sel(time=days)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in FIELDS:
        da = ds[f].astype("float32")
        units, long_name = ATTRS[f]
        da.attrs = {"units": units, "long_name": long_name,
                    "source": "ERA5-Land hourly, Earth Data Hub", "day": "UTC"}
        out = target(f, year)
        part = out.with_suffix(".part")
        da.to_netcdf(part, encoding={f: {"zlib": True, "complevel": 4}})
        part.rename(out)
    ds.close()


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    rc = Path.home() / ".edhrc"
    if not rc.exists():
        print("Missing ~/.edhrc: put the Earth Data Hub API key in it.")
        return 1
    land = Land(HUB.format(key=rc.read_text().strip()))
    for stale in list(BLOCKS.glob("*.part")) + list(OUT.glob("*.part")):
        stale.unlink()

    years = [y for y in years_from(argv) if not all(held(target(f, y)) for f in FIELDS)]
    if not years:
        log.info("rien a faire")
        return 0
    if pd.Timestamp(f"{years[-1]}-12-31T23") > land.end:
        log.info("ERA5-Land s'arrete le %s : %d incomplet", land.end, years[-1])
        return 1
    need = {y: range(land.chunk_of(pd.Timestamp(f"{y}-01-01")),
                     land.chunk_of(pd.Timestamp(f"{y}-12-31")) + 1) for y in years}
    blocks = sorted({k for ks in need.values() for k in ks})
    spatial = len(np.unique(land.rows // CHUNK_CELLS)) * (
        len(np.unique(land.west // CHUNK_CELLS)) + len(np.unique(land.east // CHUNK_CELLS)))
    log.info("%d annees (%d-%d), %d blocs de 120 jours, au plus %d lectures (%d par bloc et par variable)",
             len(years), years[0], years[-1], len(blocks), 2 * spatial * len(blocks), spatial)

    done: set[int] = set()
    for i, k in enumerate(blocks, 1):
        if not block_path(k).exists():
            t0 = time.time()
            # The hub drops requests for a few minutes at times: wait before retrying.
            for attempt, wait in ((1, 60), (2, 300), (3, None)):
                try:
                    land.write_block(k, land.read(k))
                    break
                except Exception as err:
                    log.info("[%d/%d] bloc %d essai %d echoue : %s",
                             i, len(blocks), k, attempt, type(err).__name__)
                    if wait is None:
                        log.info("abandon : relancer la meme commande reprendra ici")
                        return 1
                    time.sleep(wait)
            days = land.days_of(k)
            log.info("[%d/%d] bloc %d, %s a %s  %5.0f s  %4.0f Mo", i, len(blocks), k,
                     days[0].date(), days[-1].date(), time.time() - t0,
                     block_path(k).stat().st_size / 1e6)
        # Every year whose blocks are all there is assembled, then the blocks
        # no unwritten year needs are deleted.
        for y in years:
            if y not in done and all(block_path(j).exists() for j in need[y]):
                assemble(land, y)
                done.add(y)
                log.info("%d assemble", y)
        for j in sorted(int(p.stem.split("_")[1]) for p in BLOCKS.glob("bloc_*.nc")):
            if all(j not in need[y] or y in done for y in years):
                block_path(j).unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
