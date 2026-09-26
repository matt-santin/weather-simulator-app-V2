"""Bias-correct remapped CORDEX daily fields against ERA5, by quantile delta mapping.

    python -m src.correction.qdm tas

Run from the repo root, after src.correction.remap, with the external drive
plugged in.

Quantile delta mapping (Cannon et al. 2015, J. Climate), done for each ERA5
cell and each calendar month:

  - calibration, on CAL (1970-2005): NQ quantiles of ERA5 (Q_ref) and of
    CORDEX (Q_hist), and the bias table, b(tau) = Q_ref(tau) - Q_hist(tau)
    (additive form) or r(tau) = Q_ref(tau) / Q_hist(tau) (multiplicative);
  - correction of a day x of year Y: tau is the rank of x among the quantiles
    of CORDEX over the 30 years around Y (Y-15 to Y+14, held inside
    1970-2100), and the corrected value is x + b(tau), or x * r(tau).

The change the model gives for each quantile is thus kept, as a difference or
as a ratio, and only the bias of that quantile, measured on CAL, is removed.
Beyond the extreme quantiles, the correction of the extreme quantile applies.

VARS gives, for each variable, the ERA5 fields and their conversion to CORDEX
units (and the CORDEX fields, for the albedo, computed from two of them), the form, the physical bounds the corrected values are clipped to, and
for precipitation a trace amount: values under it, in ERA5 and CORDEX alike,
are replaced by random values between 0 and the trace before the quantiles are
taken, and corrected values under it are set to 0 (Cannon et al. 2015). The
dry-day frequency is then corrected with the rest of the distribution.

huss and rsus are not corrected here but rebuilt from corrected fields by
src.correction.derive, which also puts right the days where tasmin > tasmax.

Every year 1970-2100 is corrected; 1970-2005 serves for checks. The whole
series is first packed into a memmap on the Mac (about 10 GB, deleted at the
end), so that each month can be read across all years at once.
"""

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import xarray as xr

from src.config import ARCHIVE, DATA
from src.correction.remap import load_weights, target as remapped

OUT = ARCHIVE / "cordex" / "eur11_025_qdm"
TABLES = DATA / "correction"
ERA5_DAILY = ARCHIVE / "era5" / "daily"

YEARS = range(1970, 2101)
CAL = (1970, 2005)
WINDOW = 30
NQ = 100
LEVELS = (np.arange(NQ) + 0.5) / NQ
MAX_RATIO = 10.0  # cap on r(tau), where Q_hist is close to 0
SEED = 1  # the jitter under the trace amount is drawn the same on every run
DAY = 86400.0


@dataclass(frozen=True)
class Var:
    era5: tuple[str, ...]  # ERA5 daily fields read
    convert: Callable  # ERA5 fields, in that order, to the CORDEX variable and units
    kind: str  # "add" or "mul"
    bounds: tuple[float | None, float | None] = (None, None)
    trace: float | None = None  # "mul" only, in CORDEX units
    display: tuple[float, float, str] = (1.0, 0.0, "")  # scale, offset, unit, for printing
    cordex: tuple[str, ...] | None = None  # remapped CORDEX fields, if not the variable itself
    from_cordex: Callable | None = None  # those fields, in that order, to the variable
    derived: bool = False  # rebuilt by src.correction.derive, not corrected here


def same(x):
    return x


def albedo(up, down):
    # Under 1 W/m2 (polar night), divided by 1: the albedo is then meaningless
    # but rsus = rsds x albedo stays near 0. Same rule for ERA5 and CORDEX.
    return np.clip(up / np.maximum(down, 1), 0, 1)


K = (1.0, -273.15, "°C")
VARS = {
    "tas": Var(("t2m",), same, "add", display=K),
    "tasmax": Var(("mx2t",), same, "add", display=K),
    "tasmin": Var(("mn2t",), same, "add", display=K),
    "pr": Var(("tp",), lambda tp: tp * 1000 / DAY, "mul", (0, None), trace=1 / DAY,
              display=(DAY, 0, "mm/j")),
    "hurs": Var(("hurs",), same, "add", (0, 100), display=(1, 0, "%")),
    "huss": Var(("huss",), same, "mul", (0, None), display=(1000, 0, "g/kg"), derived=True),
    "clt": Var(("tcc",), lambda tcc: 100 * tcc, "add", (0, 100), display=(1, 0, "%")),
    "sfcWind": Var(("si10",), same, "mul", (0, None), display=(1, 0, "m/s")),
    "rsds": Var(("ssrd",), lambda s: s / DAY, "mul", (0, None), display=(1, 0, "W/m2")),
    "rlds": Var(("strd",), lambda s: s / DAY, "add", (0, None), display=(1, 0, "W/m2")),
    "rsus": Var(("ssrd", "ssr"), lambda d, n: (d - n) / DAY, "mul", (0, None),
                display=(1, 0, "W/m2"), derived=True),
    "alb": Var(("ssrd", "ssr"), lambda d, n: albedo((d - n) / DAY, d / DAY), "add", (0, 1),
               cordex=("rsus", "rsds"), from_cordex=albedo, display=(1, 0, "")),
    "ps": Var(("sp",), same, "add", display=(0.01, 0, "hPa")),
    # ERA5 counts evaporation as negative, CORDEX as positive.
    "evspsbl": Var(("e",), lambda e: -e * 1000 / DAY, "add", display=(DAY, 0, "mm/j")),
    "zg500": Var(("zg500",), same, "add", display=(1, 0, "m")),
}

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("qdm")


def window(year: int) -> tuple[int, int]:
    start = min(max(year - WINDOW // 2, YEARS[0]), YEARS[-1] - WINDOW + 1)
    return start, start + WINDOW - 1


def reference(name: str, years, cells: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """ERA5 as the CORDEX variable, (days, cells), and the month of each day."""
    v = VARS[name]
    xs, ms = [], []
    for y in years:
        das = [xr.open_dataset(ERA5_DAILY / f"{f}_ERA5_day_{y}0101-{y}1231.nc")[f]
               for f in v.era5]
        xs.append(v.convert(*[d.values.reshape(d.shape[0], -1)[:, cells] for d in das]))
        ms.append(das[0].time.dt.month.values)
    return np.concatenate(xs).astype("float32"), np.concatenate(ms)


def model(name: str, year: int) -> tuple[np.ndarray, xr.DataArray]:
    """Remapped CORDEX of that year, as (days, all cells), and a template field."""
    v = VARS[name]
    das = [xr.open_dataset(remapped(f, year))[f] for f in (v.cordex or (name,))]
    xs = [d.values.reshape(d.shape[0], -1) for d in das]
    x = v.from_cordex(*xs) if v.from_cordex else xs[0]
    return x.astype("float32"), das[0]


def jitter(x: np.ndarray, v: Var, rng: np.random.Generator) -> np.ndarray:
    """Values under the trace amount replaced by random values in (0, trace)."""
    if v.trace is None:
        return x
    low = x < v.trace
    x = x.copy()
    x[low] = rng.uniform(0, v.trace, low.sum()).astype(x.dtype)
    return x


def quantiles(x: np.ndarray) -> np.ndarray:
    """(days, points) to (NQ, points), as np.quantile (linear) but 4 times faster."""
    x = np.sort(x, axis=0)
    pos = LEVELS * (x.shape[0] - 1)
    i = np.floor(pos).astype(int)
    j = np.minimum(i + 1, x.shape[0] - 1)
    w = (pos - i)[:, None].astype("float32")
    return (1 - w) * x[i] + w * x[j]


def table(ref_q: np.ndarray, hist_q: np.ndarray, v: Var) -> np.ndarray:
    """Bias table: b(tau) for the additive form, r(tau) for the multiplicative."""
    if v.kind == "add":
        return ref_q - hist_q
    # Where CORDEX is 0 (a night of the polar winter), there is nothing to scale.
    r = np.where(hist_q > 0, ref_q / np.where(hist_q > 0, hist_q, 1), 1)
    return np.clip(r, 0, MAX_RATIO).astype("float32")


def rank(x: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Position of each x among the quantiles q, as a fractional index in [0, NQ-1].

    x is (days, points), q is (NQ, points), sorted along its first axis. A value
    equal to several quantiles (0 % or 100 % cloud cover, 0 W/m2 of sunlight)
    takes the middle of them, not the top.
    """
    le = (q[None, :, :] <= x[:, None, :]).sum(axis=1)  # quantiles below or at x
    lt = (q[None, :, :] < x[:, None, :]).sum(axis=1)  # quantiles strictly below x
    lo = np.take_along_axis(q, np.clip(le - 1, 0, NQ - 1), axis=0)
    hi = np.take_along_axis(q, np.clip(le, 0, NQ - 1), axis=0)
    gap = hi - lo
    frac = np.where(gap > 0, (x - lo) / np.where(gap > 0, gap, 1), 0)
    f = np.where(le - lt > 1, (lt + le - 1) / 2, le - 1 + frac)
    return np.clip(f, 0, NQ - 1)


def lookup(table: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Table (NQ, points) read at fractional indices f (days, points)."""
    i = np.floor(f).astype(int)
    j = np.minimum(i + 1, NQ - 1)
    w = f - i
    return (1 - w) * np.take_along_axis(table, i, axis=0) + w * np.take_along_axis(table, j, axis=0)


def apply(x: np.ndarray, sim_q: np.ndarray, tab: np.ndarray, v: Var) -> np.ndarray:
    """Days x (days, points) corrected, given the quantiles of their window."""
    c = lookup(tab, rank(x, sim_q))
    y = x + c if v.kind == "add" else x * c
    if v.trace is not None:
        y = np.where(y < v.trace, 0, y)
    lo, hi = v.bounds
    if lo is not None or hi is not None:
        y = np.clip(y, lo, hi)
    return y.astype("float32")


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in VARS or VARS[argv[0]].derived:
        print(__doc__)
        return 1
    name = argv[0]
    v = VARS[name]
    rng = np.random.default_rng(SEED)
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
        series[year == y] = model(name, y)[0][:, cells]
    series.flush()
    log.info("CORDEX lu en %.0f s", time.time() - t0)

    t0 = time.time()
    era, era_month = reference(name, range(CAL[0], CAL[1] + 1), cells)
    in_cal = (year >= CAL[0]) & (year <= CAL[1])
    log.info("ERA5 lu en %.0f s", time.time() - t0)

    ref_q = np.empty((12, NQ, cells.size), "float32")
    hist_q = np.empty((12, NQ, cells.size), "float32")
    for m in range(1, 13):
        t0 = time.time()
        ref_q[m - 1] = quantiles(jitter(era[era_month == m], v, rng))
        rows = np.flatnonzero(month == m)
        raw = jitter(np.asarray(series[rows]), v, rng)  # windows are always read raw
        hist_q[m - 1] = quantiles(raw[in_cal[rows]])
        tab = table(ref_q[m - 1], hist_q[m - 1], v)
        yr = year[rows]
        x = np.empty_like(raw)
        for y in YEARS:
            lo, hi = window(y)
            now = yr == y
            x[now] = apply(raw[now], quantiles(raw[(yr >= lo) & (yr <= hi)]), tab, v)
        series[rows] = x
        log.info("mois %02d corrige en %.0f s", m, time.time() - t0)
    del era
    series.flush()

    grid = model(name, YEARS[0])[1]
    lat, lon = grid.latitude, grid.longitude
    xr.Dataset(
        {"ref": (("month", "quantile", "cell"), ref_q),
         "hist": (("month", "quantile", "cell"), hist_q)},
        coords={"month": np.arange(1, 13), "quantile": LEVELS, "cell": cells},
        attrs={"ref": f"ERA5 {', '.join(v.era5)}, in CORDEX units", "hist": f"CORDEX {name} remapped",
               "kind": v.kind, "period": f"{CAL[0]}-{CAL[1]}", "grid": "ERA5 0.25 deg",
               "cell": "flat index into (latitude, longitude)",
               "latitude": lat.values, "longitude": lon.values},
    ).to_netcdf(TABLES / f"{name}_quantiles_{CAL[0]}-{CAL[1]}.nc")

    form = "additive" if v.kind == "add" else f"multiplicative, ratio capped at {MAX_RATIO:g}"
    for y in YEARS:
        src = model(name, y)[1]
        out = np.full((src.time.size, keep.size), np.nan, "float32")
        out[:, cells] = series[year == y]
        da = src.copy(data=out.reshape(src.shape)).rename(name)
        if v.cordex:
            da.attrs = {"units": "1", "long_name": f"{name}, from {' and '.join(v.cordex)}"}
        da.attrs["bias_correction"] = (
            f"QDM {form} (Cannon 2015) against ERA5 {', '.join(v.era5)}, "
            f"{CAL[0]}-{CAL[1]}, per calendar month, {NQ} quantiles, "
            f"{WINDOW}-year sliding window"
            + (f", trace amount {v.trace:g} {da.attrs.get('units', '')}" if v.trace else "")
            + (f", clipped to {v.bounds}" if v.bounds != (None, None) else ""))
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
