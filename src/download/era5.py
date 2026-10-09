"""Pull ERA5 from Earth Data Hub and reduce it to daily values on the EUR-11 box.

    python -m src.download.era5 1970
    python -m src.download.era5 1970-2005
    python -m src.download.era5 lsm          fixed fields, once

Run from the repo root. Needs the Earth Data Hub API key in ~/.edhrc.

Earth Data Hub serves ERA5 hourly as Zarr, with no queue, where the CDS kept a
single request waiting for hours. It bills every chunk read, 500 000 a month:
a chunk spans 45 days x 15 deg x 15 deg (60 days for pressure levels), and the
box covers 32 of them in space. A variable is therefore read over the whole
year in one piece, never month by month, so that no chunk is read twice.

Only daily values are kept, one file per variable and year, in ERA5 units. The
hourly data is reduced in memory and never stored. Three fields are derived
here because only the hourly data gives them exactly: wind speed (the speed of
the daily mean wind is not the daily mean speed), hurs and huss (both are
non-linear in temperature and dew point).

Days are UTC days, as in CORDEX. Accumulations and extremes are stamped at the
end of the hour they cover, so they are moved back one hour: the day then
takes 00h-01h to 23h-24h, which needs 00h of the next day.

Anything already on disk is skipped, so the run is resumable.
"""

import logging
import sys
import time
from pathlib import Path

import dask
import numpy as np
import xarray as xr

from src.config import ERA5, held

OUT = ERA5 / "daily"
HUB = "https://edh:{key}@data.earthdatahub.destine.eu/era5/"
SINGLE = "era5-single-levels-atmosphere-v0.zarr"
PRESSURE = "era5-pressure-levels-v0.zarr"

# North, west, south, east: the smallest 0.25 deg box around the EUR-11 grid.
NORTH, WEST, SOUTH, EAST = 73.0, -45.0, 21.75, 65.25
G = 9.80665

# name: (source variables, statistic). "accum" and "max"/"min" fields are
# shifted back one hour before the daily reduction.
DAILY = {
    "t2m": (["t2m"], "mean"),
    "mx2t": (["mx2t"], "max"),
    "mn2t": (["mn2t"], "min"),
    "d2m": (["d2m"], "mean"),
    "tp": (["tp"], "sum"),
    "tcc": (["tcc"], "mean"),
    "ssrd": (["ssrd"], "sum"),
    "strd": (["strd"], "sum"),
    "ssr": (["ssr"], "sum"),
    "sp": (["sp"], "mean"),
    # Mean sea-level pressure, for the isobars of the maps.
    "msl": (["msl"], "mean"),
    "e": (["e"], "sum"),
    "si10": (["u10", "v10"], "mean"),
    "hurs": (["t2m", "d2m"], "mean"),
    "huss": (["d2m", "sp"], "mean"),
    "zg500": (["z"], "mean"),
    # Sea-ice markers, as Earth Data Hub has no sea-ice cover: sst sits at its
    # floor, -1.65 C, under ice, and istl1 is -1.65 C exactly where there is
    # no ice. Both are missing over land.
    "sst": (["sst"], "mean"),
    "istl1": (["istl1"], "mean"),
}
# Fields that do not change in time: one hour is read, 1970-01-01 00h.
FIXED = {
    "lsm": ("1", "land-sea mask, fraction of land"),
    # Orography: altitude of the ERA5 cells, to set against the station grid of E-OBS.
    "z": ("m2 s-2", "surface geopotential"),
}
SHIFTED = {"tp", "ssrd", "strd", "ssr", "e", "mx2t", "mn2t"}
# Fields that share hourly sources are computed together, so that dask reads
# each chunk once: t2m, d2m and sp would otherwise be billed two or three times.
GROUPS = [("t2m", "d2m", "sp", "hurs", "huss")] + [
    (n,) for n in DAILY if n not in {"t2m", "d2m", "sp", "hurs", "huss"}]

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("era5")


def saturation(t: xr.DataArray) -> xr.DataArray:
    # Saturation vapour pressure over water, in Pa, Tetens form used by the IFS.
    return 611.21 * np.exp(17.502 * (t - 273.16) / (t - 32.19))


def box(da: xr.DataArray) -> xr.DataArray:
    # Longitudes run 0..360 and the box crosses Greenwich: take both sides.
    da = da.sel(latitude=slice(NORTH, SOUTH))
    west = da.sel(longitude=slice(360 + WEST, 359.75))
    west = west.assign_coords(longitude=west.longitude - 360)
    return xr.concat([west, da.sel(longitude=slice(0, EAST))], dim="longitude")


def target(name: str, year: int) -> Path:
    return OUT / f"{name}_ERA5_day_{year}0101-{year}1231.nc"


def daily(sources: dict[str, xr.Dataset], name: str, year: int) -> xr.DataArray:
    fields, stat = DAILY[name]
    shift = name in SHIFTED
    start = f"{year}-01-01T01" if shift else f"{year}-01-01"
    end = f"{year + 1}-01-01T00" if shift else f"{year}-12-31T23"

    def get(v: str) -> xr.DataArray:
        ds = sources["pressure"] if v == "z" else sources["single"]
        da = ds[v]
        if v == "z":
            da = da.sel(isobaricInhPa=500).drop_vars("isobaricInhPa")
        da = box(da.sel(valid_time=slice(start, end)))
        if shift:
            da = da.assign_coords(valid_time=da.valid_time - np.timedelta64(1, "h"))
        return da

    if name == "si10":
        hourly = np.hypot(get("u10"), get("v10"))
    elif name == "hurs":
        hourly = (100 * saturation(get("d2m")) / saturation(get("t2m"))).clip(max=100)
    elif name == "huss":
        e = saturation(get("d2m"))
        hourly = 0.622 * e / (get("sp") - 0.378 * e)
    elif name == "zg500":
        hourly = get("z") / G
    else:
        hourly = get(fields[0])

    day = getattr(hourly.resample(valid_time="1D"), stat)()
    return day.rename(name).rename({"valid_time": "time"}).astype("float32")


def attrs(da: xr.DataArray, sources: dict[str, xr.Dataset]) -> xr.DataArray:
    fields, stat = DAILY[da.name]
    extra = {
        "si10": ("m s**-1", "10 m wind speed, daily mean of hourly speed"),
        "hurs": ("%", "2 m relative humidity over water, daily mean of hourly values"),
        "huss": ("kg kg**-1", "2 m specific humidity, daily mean of hourly values"),
        "zg500": ("m", "geopotential height at 500 hPa, daily mean"),
    }
    if da.name in extra:
        units, long_name = extra[da.name]
    else:
        src = sources["single"][fields[0]].attrs
        units, long_name = src.get("units"), f"{src.get('long_name')}, daily {stat}"
    da.attrs = {"units": units, "long_name": long_name,
                "source": "ERA5 hourly, Earth Data Hub", "day": "UTC"}
    return da


def fixed(sources: dict[str, xr.Dataset], name: str) -> None:
    out = ERA5 / "fixed" / f"{name}_ERA5.nc"
    if held(out):
        log.info("%s deja present", out.name)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    da = box(sources["single"][name].sel(valid_time="1970-01-01T00")).drop_vars(
        "valid_time").astype("float32").compute()
    units, long_name = FIXED[name]
    da.attrs = {"units": units, "long_name": long_name, "source": "ERA5, Earth Data Hub"}
    part = out.with_suffix(".part")
    da.to_netcdf(part)
    part.rename(out)
    log.info("%s ecrit", out)


def years_from(argv: list[str]) -> list[int]:
    out: list[int] = []
    for a in argv:
        if "-" in a:
            lo, hi = a.split("-")
            out += list(range(int(lo), int(hi) + 1))
        else:
            out.append(int(a))
    return sorted(set(out))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    rc = Path.home() / ".edhrc"
    if not rc.exists():
        print("Missing ~/.edhrc: put the Earth Data Hub API key in it.")
        return 1
    url = HUB.format(key=rc.read_text().strip())

    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.part"):
        stale.unlink()

    sources = {
        "single": xr.open_dataset(url + SINGLE, engine="zarr", chunks={}),
        "pressure": xr.open_dataset(url + PRESSURE, engine="zarr", chunks={}),
    }

    if set(argv) <= set(FIXED):
        for name in argv:
            fixed(sources, name)
        return 0

    ys = years_from(argv)
    todo = [(y, g) for y in ys for g in GROUPS]
    log.info("%d annees (%d-%d) x %d variables en %d lots",
             len(ys), ys[0], ys[-1], len(DAILY), len(todo))
    failed: list[tuple[int, tuple[str, ...]]] = []
    for i, (y, group) in enumerate(todo, 1):
        if all(held(target(n, y)) for n in group):
            continue
        t0 = time.time()
        # A read can fail on a dropped connection. Chunks already read are not
        # kept, so a retry costs the whole lot again: two tries only.
        for attempt in (1, 2):
            try:
                results = dask.compute(*[daily(sources, n, y) for n in group])
                for da in results:
                    out = target(da.name, y)
                    part = out.with_suffix(".part")
                    attrs(da, sources).to_netcdf(
                        part, encoding={da.name: {"zlib": True, "complevel": 4}})
                    part.rename(out)
                break
            except Exception as err:
                log.info("[%d/%d] %d %s essai %d echoue : %s",
                         i, len(todo), y, ",".join(group), attempt, type(err).__name__)
                if attempt == 2:
                    failed.append((y, group))
        else:
            continue
        size = sum(target(n, y).stat().st_size for n in group) / 1e6
        log.info("[%d/%d] %d %-24s %5.0f s  %4.0f Mo",
                 i, len(todo), y, ",".join(group), time.time() - t0, size)

    if failed:
        log.info("%d echecs, a relancer : %s", len(failed), failed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
