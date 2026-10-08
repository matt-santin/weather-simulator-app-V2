"""Bias-correct remapped CORDEX daily fields against ERA5, by quantile delta mapping.

    python -m src.correction.qdm tas
    WSA_MODEL=mpi python -m src.correction.qdm tas   (src.correction.models)

Run from the repo root, after src.correction.remap, with the external drive
plugged in.

Quantile delta mapping (Cannon et al. 2015, J. Climate), done for each ERA5
cell and each calendar month:

  - calibration, on CAL (1970 to the last historical year of the run: 1970-2005
    for RCA4, 1970-2014 for MPI / ICON): NQ quantiles of ERA5 (Q_ref) and of
    CORDEX (Q_hist), and the bias table, b(tau) = Q_ref(tau) - Q_hist(tau)
    (additive form), or the pair Q_ref, Q_hist themselves (multiplicative);
  - correction of a day x of year Y: tau is the rank of x among the quantiles
    of CORDEX over the 30 years around Y (Y-15 to Y+14, held inside
    1970-2100), and the corrected value is x + b(tau), or
    Q_ref(tau) * x / Q_hist(tau): the ERA5 quantile times the change the
    model gives at that rank, capped at MAX_RATIO. Q_ref and Q_hist are read
    at tau apart, not their ratio, which jumps between quantiles near 0.

The change the model gives for each quantile is thus kept, as a difference or
as a ratio, and only the bias of that quantile, measured on CAL, is removed.
Beyond the extreme quantiles, the correction of the extreme quantile applies.

VARS gives, for each variable, the ERA5 fields and their conversion to CORDEX
units (and the CORDEX fields, for the albedo, computed from two of them), the
form and the physical bounds the corrected values are clipped to.

Precipitation is corrected in two steps, occurrence then intensity (frequency
adaptation of Themessl et al. 2012, as in xclim/xsdba, then QDM on wet days):

  - occurrence: for each cell and month, the model threshold is the value
    that leaves under it, on CAL, the share of days ERA5 has under its wet
    threshold (1 mm/day). The same threshold serves 1970-2100, so the change in the
    number of wet days the model gives is kept. Days under it are set to 0:
    the days that switch are chosen by their amount, not at random. Where
    the model has more days at exactly 0 than ERA5 has dry days, the
    threshold is its smallest positive value: all its wet days are kept, and
    it stays too dry;
  - intensity: multiplicative QDM between the wet days of the model (at or
    above the threshold) and those of ERA5 (at or above 1 mm/day), quantiles
    taken without the dry days. Where ERA5 or the model has fewer than
    MIN_WET wet days on CAL, wet days keep their raw amount.

huss and rsus are not corrected here but rebuilt from corrected fields by
src.correction.derive, which also puts right the days where tasmin > tasmax.

Every year 1970-2100 is corrected; CAL serves for checks. With
WSA_QDM_TEST=1, files and tables go to test folders (eur11_025_qdm_test,
data/correction/test), which src.correction.check, spells and violin then
read. The whole series is first packed into a memmap on the Mac (about
10 GB, deleted at the end), so that each month can be read across all years
at once.
"""

import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import xarray as xr

from src.config import ARCHIVE, DATA
from src.correction.models import MODEL
from src.correction.remap import load_weights, target as remapped

TEST = os.environ.get("WSA_QDM_TEST") == "1"
OUT = ARCHIVE / "cordex" / (f"{MODEL.out}_025_qdm" + ("_test" if TEST else ""))
TABLES = DATA / "correction" / MODEL.tables / ("test" if TEST else "")
ERA5_DAILY = ARCHIVE / "era5" / "daily"

YEARS = range(1970, 2101)
CAL = (1970, MODEL.hist_end)
# Split sample of the checks: CAL cut in two halves (1970-1987 and 1988-2005 for RCA4).
SPLIT = (CAL[0] + CAL[1] + 1) // 2
HALVES = (range(CAL[0], SPLIT), range(SPLIT, CAL[1] + 1))
LABELS = tuple(f"{h[0]}-{h[-1]}" for h in HALVES)
WINDOW = 30
NQ = 100
LEVELS = (np.arange(NQ) + 0.5) / NQ
MAX_RATIO = 10.0  # cap on x / Q_hist(tau), the change the model gives, multiplicative form
MIN_WET = 30  # wet days on CAL, in ERA5 and the model, under which amounts stay raw
DAY = 86400.0


@dataclass(frozen=True)
class Var:
    era5: tuple[str, ...]  # ERA5 daily fields read
    convert: Callable  # ERA5 fields, in that order, to the CORDEX variable and units
    kind: str  # "add" or "mul"
    bounds: tuple[float | None, float | None] = (None, None)
    wet: float | None = None  # ERA5 wet-day threshold, in CORDEX units: occurrence then intensity
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
    "pr": Var(("tp",), lambda tp: tp * 1000 / DAY, "mul", (0, None), wet=1 / DAY,
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


def quantiles(x: np.ndarray) -> np.ndarray:
    """(days, points) to (NQ, points), as np.nanquantile (linear) but faster.

    NaN (dry days, for precipitation) are left out; a point with no value
    gets NaN quantiles.
    """
    x = np.sort(x, axis=0)  # NaN last
    top = np.maximum((~np.isnan(x)).sum(0) - 1, 0)  # index of the last value, per point
    pos = LEVELS[:, None] * top
    i = np.floor(pos).astype(int)
    j = np.minimum(i + 1, top)
    w = (pos - i).astype("float32")
    return (1 - w) * np.take_along_axis(x, i, axis=0) + w * np.take_along_axis(x, j, axis=0)


def threshold(ref: np.ndarray, hist: np.ndarray, wet: float) -> np.ndarray:
    """Model threshold (points,) leaving under it the share of days ERA5 has under wet."""
    n = hist.shape[0]
    dry = np.round((ref < wet).mean(0) * n).astype(int)  # model days to set dry
    s = np.sort(hist, axis=0)
    th = np.take_along_axis(s, np.minimum(dry, n - 1)[None], axis=0)[0]
    th = np.where(dry < n, th, np.inf)
    # Model too dry: not enough days above 0, all of them are kept.
    smallest = np.where(s > 0, s, np.inf).min(0)
    return np.maximum(th, smallest).astype("float32")


def calibrate(ref: np.ndarray, hist: np.ndarray, v: Var) -> dict[str, np.ndarray]:
    """Calibration of one month from ERA5 and CORDEX (days, points) on CAL:
    quantiles of both, (NQ, points), and for precipitation the model threshold
    and the number of wet days of each, (points,)."""
    if v.wet is None:
        return {"ref": quantiles(ref), "hist": quantiles(hist)}
    th = threshold(ref, hist, v.wet)
    ref_wet, hist_wet = ref >= v.wet, hist >= th
    return {"ref": quantiles(np.where(ref_wet, ref, np.nan)),
            "hist": quantiles(np.where(hist_wet, hist, np.nan)),
            "threshold": th, "n_ref": ref_wet.sum(0), "n_hist": hist_wet.sum(0)}


def table(ref_q: np.ndarray, hist_q: np.ndarray, v: Var) -> np.ndarray:
    """Bias table: b(tau) (NQ, points) for the additive form, Q_ref and Q_hist
    stacked (2, NQ, points) for the multiplicative."""
    if v.kind == "add":
        return ref_q - hist_q
    return np.stack([ref_q, hist_q])


def ratio(tab: np.ndarray) -> np.ndarray:
    """r(tau) = Q_ref / Q_hist of a multiplicative table, for display."""
    ref_q, hist_q = tab
    return np.where(hist_q > 0, ref_q / np.where(hist_q > 0, hist_q, 1), 1)


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
    f = rank(x, sim_q)
    if v.kind == "add":
        y = x + lookup(tab, f)
    else:
        ref, hist = lookup(tab[0], f), lookup(tab[1], f)
        # Where CORDEX is 0 (a night of the polar winter), there is nothing to scale.
        change = np.clip(x / np.where(hist > 0, hist, 1), 0, MAX_RATIO)
        y = np.where(hist > 0, ref * change, x)
    lo, hi = v.bounds
    if lo is not None or hi is not None:
        y = np.clip(y, lo, hi)
    return y.astype("float32")


def correct(x: np.ndarray, win: np.ndarray, cal: dict[str, np.ndarray], v: Var) -> np.ndarray:
    """Days x (days, points) of one month and year corrected, given the raw
    CORDEX days of that month over their window, win, and the calibration."""
    tab = table(cal["ref"], cal["hist"], v)
    if v.wet is None:
        return apply(x, quantiles(win), tab, v)
    th = cal["threshold"]
    y = np.where(x >= th, x, 0).astype("float32")
    sim_q = quantiles(np.where(win >= th, win, np.nan))
    # Enough wet days on CAL, and at least one in the window (then x has some).
    ok = (cal["n_ref"] >= MIN_WET) & (cal["n_hist"] >= MIN_WET) & ~np.isnan(sim_q[0])
    fixed = apply(x[:, ok], sim_q[:, ok], tab[:, :, ok], v)
    y[:, ok] = np.where(x[:, ok] >= th[ok], fixed, 0)
    return y


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in VARS or VARS[argv[0]].derived:
        print(__doc__)
        return 1
    name = argv[0]
    v = VARS[name]
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

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

    cal = []
    for m in range(1, 13):
        t0 = time.time()
        rows = np.flatnonzero(month == m)
        raw = np.asarray(series[rows])  # windows are always read raw
        cal.append(calibrate(era[era_month == m], raw[in_cal[rows]], v))
        yr = year[rows]
        x = np.empty_like(raw)
        for y in YEARS:
            lo, hi = window(y)
            now = yr == y
            x[now] = correct(raw[now], raw[(yr >= lo) & (yr <= hi)], cal[-1], v)
        series[rows] = x
        log.info("mois %02d corrige en %.0f s", m, time.time() - t0)
    del era
    series.flush()

    grid = model(name, YEARS[0])[1]
    lat, lon = grid.latitude, grid.longitude
    dims = {2: ("month", "cell"), 3: ("month", "quantile", "cell")}
    tables = {k: np.stack([c[k] for c in cal]) for k in cal[0]}
    xr.Dataset(
        {k: (dims[a.ndim], a) for k, a in tables.items()},
        coords={"month": np.arange(1, 13), "quantile": LEVELS, "cell": cells},
        attrs={"ref": f"ERA5 {', '.join(v.era5)}, in CORDEX units", "hist": f"CORDEX {name} remapped",
               "kind": v.kind, "period": f"{CAL[0]}-{CAL[1]}", "grid": "ERA5 0.25 deg",
               "cell": "flat index into (latitude, longitude)",
               "latitude": lat.values, "longitude": lon.values}
        | ({"threshold": "model wet-day threshold", "n_ref": "ERA5 wet days on CAL",
            "n_hist": "model wet days on CAL", "wet": f"ERA5 wet day: >= {v.wet:g}",
            "quantiles": "wet days only"} if v.wet else {}),
    ).to_netcdf(TABLES / f"{name}_quantiles_{CAL[0]}-{CAL[1]}.nc")

    form = "additive" if v.kind == "add" else f"multiplicative, model change capped at {MAX_RATIO:g}"
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
            + (f", occurrence first (model threshold matching ERA5 days under {v.wet:g} "
               f"{da.attrs.get('units', '')}), then wet days only, raw amounts under "
               f"{MIN_WET} wet days" if v.wet else "")
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
