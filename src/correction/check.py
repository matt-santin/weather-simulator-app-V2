"""Checks of the QDM correction, printed and drawn in data/correction/.

    python -m src.correction.check tas

1. Split sample: calibrate on 1970-1987, correct 1988-2005 (its own 18 years
   as the model distribution), compare with ERA5 1988-2005. Scores per month,
   over the cells, for the mean and the 5th and 95th percentiles.
2. Change signal: 2071-2100 minus 1976-2005, raw against corrected, for the
   mean and the 95th percentile. QDM should keep it.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from src.config import ARCHIVE, DATA
from src.correction.qdm import ERA5_NAME, OUT, lookup, quantiles, rank
from src.correction.remap import load_weights, target as remapped

FIG = DATA / "correction"


def load(paths, name, cells):
    """Stack yearly files as (days, cells) plus the month of each day."""
    xs, ms = [], []
    for p in paths:
        da = xr.open_dataset(p)[name]
        xs.append(da.values.reshape(da.shape[0], -1)[:, cells])
        ms.append(da.time.dt.month.values)
    return np.concatenate(xs), np.concatenate(ms)


def era5(name, years, cells):
    v = ERA5_NAME[name]
    return load([ARCHIVE / "era5" / "daily" / f"{v}_ERA5_day_{y}0101-{y}1231.nc" for y in years],
                v, cells)


def stats(x):
    return np.stack([x.mean(0), np.percentile(x, 5, axis=0), np.percentile(x, 95, axis=0)])


def split_sample(name, cells, shape):
    cal, val = range(1970, 1988), range(1988, 2006)
    ref_c, mc = era5(name, cal, cells)
    ref_v, mv = era5(name, val, cells)
    hist_c, _ = load([remapped(name, y) for y in cal], name, cells)
    sim_v, _ = load([remapped(name, y) for y in val], name, cells)
    print("Validation croisee (calibre 1970-1987, teste 1988-2005), ecart au ERA5 en K")
    print("mois | moyenne brut/corrige (biais moyen, RMS sur les mailles) | P5 | P95")
    maps = []
    for m in range(1, 13):
        bias = quantiles(ref_c[mc == m]) - quantiles(hist_c[mc == m])
        x = sim_v[mv == m]
        corr = x + lookup(bias, rank(x, quantiles(x)))
        e = stats(ref_v[mv == m])
        raw, fix = stats(x) - e, stats(corr) - e
        cols = []
        for k in range(3):
            cols.append("%+5.2f/%+5.2f (%4.2f/%4.2f)" % (
                raw[k].mean(), fix[k].mean(), np.sqrt((raw[k] ** 2).mean()),
                np.sqrt((fix[k] ** 2).mean())))
        print("%4d | %s" % (m, " | ".join(cols)))
        if m in (1, 7):
            maps += [(f"mois {m}, P95 brut - ERA5", raw[2]), (f"mois {m}, P95 corrige - ERA5", fix[2])]
    return maps


def signal(name, cells):
    past, fut = range(1976, 2006), range(2071, 2101)
    print("\nSignal 2071-2100 moins 1976-2005, moyenne sur les mailles, en K")
    print("mois | moyenne brut/corrige (ecart max sur les mailles) | P95")
    # One 30-year series at a time: four of them would not fit in memory.
    s = {}
    for key, years in (("past", past), ("fut", fut)):
        for kind, path in (("raw", remapped), ("cor", lambda n, y: OUT / remapped(n, y).name)):
            x, mo = load([path(name, y) for y in years], name, cells)
            s[kind, key] = [stats(x[mo == m]) for m in range(1, 13)]
            del x
    for m in range(1, 13):
        dr = s["raw", "fut"][m - 1] - s["raw", "past"][m - 1]
        dc = s["cor", "fut"][m - 1] - s["cor", "past"][m - 1]
        print("%4d | %5.2f/%5.2f (%4.2f) | %5.2f/%5.2f (%4.2f)" % (
            m, dr[0].mean(), dc[0].mean(), np.abs(dc[0] - dr[0]).max(),
            dr[2].mean(), dc[2].mean(), np.abs(dc[2] - dr[2]).max()))


def main(argv):
    if len(argv) != 1 or argv[0] not in ERA5_NAME:
        print(__doc__)
        return 1
    name = argv[0]
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    grid = xr.open_dataset(remapped(name, 1970))
    maps = split_sample(name, cells, keep.shape)
    signal(name, cells)

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    for ax, (title, v) in zip(axes.flat, maps):
        full = np.full(keep.size, np.nan)
        full[cells] = v
        im = ax.pcolormesh(grid.longitude, grid.latitude, full.reshape(keep.shape),
                           cmap="RdBu_r", vmin=-5, vmax=5)
        ax.set_title(title + " (K), 1988-2005")
    fig.colorbar(im, ax=axes, shrink=0.8)
    path = FIG / f"{name}_validation.png"
    fig.savefig(path, dpi=90)
    print("\ncartes :", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
