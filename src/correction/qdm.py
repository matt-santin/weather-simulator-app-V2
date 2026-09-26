"""Bias-correct remapped CORDEX daily fields against ERA5, by quantile delta mapping.

    python -m src.correction.qdm tas

Run from the repo root, after src.correction.remap, with the external drive
plugged in.

Quantile delta mapping (Cannon et al. 2015, J. Climate), additive form, done
for each ERA5 cell and each calendar month:

  - calibration, on CAL (1970-2005): NQ quantiles of ERA5 (Q_ref) and of
    CORDEX (Q_hist), and the bias table b(tau) = Q_ref(tau) - Q_hist(tau);
  - correction of a day x of year Y: tau is the rank of x among the quantiles
    of CORDEX over the 30 years around Y (Y-15 to Y+14, held inside
    1970-2100), and the corrected value is x + b(tau).

The change the model gives for each quantile is thus kept, and only the bias
of that quantile, measured on CAL, is removed. Beyond the extreme quantiles,
the correction of the extreme quantile applies.

Every year 1970-2100 is corrected; 1970-2005 serves for checks. The whole
series is first packed into a memmap on the Mac (about 10 GB, deleted at the
end), so that each month can be read across all years at once.
"""

import logging
import sys
import time

import numpy as np
import xarray as xr

from src.config import ARCHIVE, DATA
from src.correction.remap import load_weights, target as remapped

OUT = ARCHIVE / "cordex" / "eur11_025_qdm"
TABLES = DATA / "correction"
ERA5_NAME = {"tas": "t2m"}

YEARS = range(1970, 2101)
CAL = (1970, 2005)
WINDOW = 30
NQ = 100
LEVELS = (np.arange(NQ) + 0.5) / NQ

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("qdm")


def window(year: int) -> tuple[int, int]:
    start = min(max(year - WINDOW // 2, YEARS[0]), YEARS[-1] - WINDOW + 1)
    return start, start + WINDOW - 1


def quantiles(x: np.ndarray) -> np.ndarray:
    """(days, points) to (NQ, points), as np.quantile (linear) but 4 times faster."""
    x = np.sort(x, axis=0)
    pos = LEVELS * (x.shape[0] - 1)
    i = np.floor(pos).astype(int)
    j = np.minimum(i + 1, x.shape[0] - 1)
    w = (pos - i)[:, None].astype("float32")
    return (1 - w) * x[i] + w * x[j]


def rank(x: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Position of each x among the quantiles q, as a fractional index in [0, NQ-1].

    x is (days, points), q is (NQ, points), sorted along its first axis.
    """
    k = (q[None, :, :] <= x[:, None, :]).sum(axis=1)  # quantiles below x
    lo = np.take_along_axis(q, np.clip(k - 1, 0, NQ - 1), axis=0)
    hi = np.take_along_axis(q, np.clip(k, 0, NQ - 1), axis=0)
    gap = hi - lo
    frac = np.where(gap > 0, (x - lo) / np.where(gap > 0, gap, 1), 0)
    return np.clip(k - 1 + frac, 0, NQ - 1)


def lookup(table: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Table (NQ, points) read at fractional indices f (days, points)."""
    i = np.floor(f).astype(int)
    j = np.minimum(i + 1, NQ - 1)
    w = f - i
    return (1 - w) * np.take_along_axis(table, i, axis=0) + w * np.take_along_axis(table, j, axis=0)


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ERA5_NAME:
        print(__doc__)
        return 1
    name = argv[0]
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    OUT.mkdir(parents=True, exist_ok=True)

    # All days of all years, as (days, cells), with their dates.
    days = np.concatenate([np.arange(f"{y}-01-01", f"{y + 1}-01-01", dtype="datetime64[D]")
                           for y in YEARS])
    year = days.astype("datetime64[Y]").astype(int) + 1970
    month = days.astype("datetime64[M]").astype(int) % 12 + 1
    pack = TABLES / f"{name}_pack.tmp"
    series = np.lib.format.open_memmap(pack, mode="w+", dtype="float32",
                                       shape=(days.size, cells.size))
    t0 = time.time()
    for y in YEARS:
        da = xr.open_dataset(remapped(name, y))[name]
        series[year == y] = da.values.reshape(da.shape[0], -1)[:, cells]
    series.flush()
    log.info("CORDEX lu en %.0f s", time.time() - t0)

    t0 = time.time()
    era = np.concatenate([
        xr.open_dataset(ARCHIVE / "era5" / "daily" /
                        f"{ERA5_NAME[name]}_ERA5_day_{y}0101-{y}1231.nc")[ERA5_NAME[name]]
        .values.reshape(-1, keep.size)[:, cells]
        for y in range(CAL[0], CAL[1] + 1)])
    in_cal = (year >= CAL[0]) & (year <= CAL[1])
    log.info("ERA5 lu en %.0f s", time.time() - t0)

    ref_q = np.empty((12, NQ, cells.size), "float32")
    hist_q = np.empty((12, NQ, cells.size), "float32")
    for m in range(1, 13):
        t0 = time.time()
        ref_q[m - 1] = quantiles(era[month[in_cal] == m])
        rows = np.flatnonzero(month == m)
        x = np.asarray(series[rows])
        hist_q[m - 1] = quantiles(x[in_cal[rows]])
        bias = ref_q[m - 1] - hist_q[m - 1]
        yr = year[rows]
        raw = x.copy()  # windows are read raw, never from years already corrected
        for y in YEARS:
            lo, hi = window(y)
            sim_q = quantiles(raw[(yr >= lo) & (yr <= hi)])
            now = yr == y
            x[now] = raw[now] + lookup(bias, rank(raw[now], sim_q))
        series[rows] = x
        log.info("mois %02d corrige en %.0f s", m, time.time() - t0)
    del era
    series.flush()

    lat = xr.open_dataset(remapped(name, YEARS[0])).latitude
    lon = xr.open_dataset(remapped(name, YEARS[0])).longitude
    xr.Dataset(
        {"ref": (("month", "quantile", "cell"), ref_q),
         "hist": (("month", "quantile", "cell"), hist_q)},
        coords={"month": np.arange(1, 13), "quantile": LEVELS, "cell": cells},
        attrs={"ref": f"ERA5 {ERA5_NAME[name]}", "hist": f"CORDEX {name} remapped",
               "period": f"{CAL[0]}-{CAL[1]}", "grid": "ERA5 0.25 deg",
               "cell": "flat index into (latitude, longitude)",
               "latitude": lat.values, "longitude": lon.values},
    ).to_netcdf(TABLES / f"{name}_quantiles_{CAL[0]}-{CAL[1]}.nc")

    for y in YEARS:
        src = xr.open_dataset(remapped(name, y))
        out = np.full((src.time.size, keep.size), np.nan, "float32")
        out[:, cells] = series[year == y]
        da = src[name].copy(data=out.reshape(src[name].shape))
        da.attrs["bias_correction"] = (
            f"QDM additive (Cannon 2015) against ERA5 {ERA5_NAME[name]}, "
            f"{CAL[0]}-{CAL[1]}, per calendar month, {NQ} quantiles, "
            f"{WINDOW}-year sliding window")
        path = OUT / remapped(name, y).name
        part = path.with_suffix(".part")
        da.to_netcdf(part, encoding={name: {"zlib": True, "complevel": 4}})
        part.rename(path)
    del series
    pack.unlink()
    log.info("fichiers corriges ecrits dans %s", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
