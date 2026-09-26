"""Checks of the QDM correction, printed and drawn in data/correction/.

    python -m src.correction.check tas

1. Split sample: calibrate on 1970-1987, correct 1988-2005 (its own 18 years
   as the model distribution), compare with ERA5 1988-2005. Scores per month,
   over the cells, for the mean and the 5th and 95th percentiles, in the
   display unit of the variable. For precipitation, the dry-day frequency too;
   for bounded variables, the share of days at a bound. Derived variables
   (huss, rsus) are rebuilt from fields calibrated on 1970-2005: their files
   are compared as they are, so 1988-2005 is not independent there.
2. Change signal: 2071-2100 against 1976-2005, raw against corrected, for the
   mean and the 95th percentile, as a difference (additive form) or in %
   (multiplicative). QDM should keep it.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from src.config import DATA
from src.correction.qdm import OUT, SEED, VARS, apply, jitter, model, quantiles, reference, table
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


def raw(name, years, cells):
    xs, ms = [], []
    for y in years:
        x, grid = model(name, y)
        xs.append(x[:, cells])
        ms.append(grid.time.dt.month.values)
    return np.concatenate(xs), np.concatenate(ms)


def corrected(name, years, cells):
    return load([OUT / remapped(name, y).name for y in years], name, cells)


def stats(x):
    return np.stack([x.mean(0), np.percentile(x, 5, axis=0), np.percentile(x, 95, axis=0)])


def at_bound(x, v):
    """Share of days at a bound, lower and upper, in %."""
    lo, hi = v.bounds
    return [100 * np.mean(x <= b) if k == 0 else 100 * np.mean(x >= b)
            for k, b in enumerate((lo, hi)) if b is not None]


def split_sample(name, cells):
    v = VARS[name]
    scale, unit = v.display[0], v.display[2].replace("°C", "K")  # differences
    rng = np.random.default_rng(SEED)
    cal, val = range(1970, 1988), range(1988, 2006)
    ref_c, mc = reference(name, cal, cells)
    ref_v, mv = reference(name, val, cells)
    hist_c, _ = raw(name, cal, cells)
    sim_v, _ = raw(name, val, cells)
    if v.derived:
        cor_v, _ = corrected(name, val, cells)
        print(f"Variable derivee, fichiers corriges (calibres 1970-2005), 1988-2005, ecart au ERA5 en {unit}")
    else:
        print(f"Validation croisee (calibre 1970-1987, teste 1988-2005), ecart au ERA5 en {unit}")
    print("mois | moyenne brut/corrige (biais moyen, RMS sur les mailles) | P5 | P95")
    maps, extra = [], []
    for m in range(1, 13):
        if v.derived:
            corr = cor_v[mv == m]
        else:
            tab = table(quantiles(jitter(ref_c[mc == m], v, rng)),
                        quantiles(jitter(hist_c[mc == m], v, rng)), v)
            x = jitter(sim_v[mv == m], v, rng)
            corr = apply(x, quantiles(x), tab, v)
        x = sim_v[mv == m]
        e = stats(ref_v[mv == m])
        raw, fix = scale * (stats(x) - e), scale * (stats(corr) - e)
        cols = []
        for k in range(3):
            cols.append("%+6.2f/%+6.2f (%5.2f/%5.2f)" % (
                raw[k].mean(), fix[k].mean(), np.sqrt((raw[k] ** 2).mean()),
                np.sqrt((fix[k] ** 2).mean())))
        print("%4d | %s" % (m, " | ".join(cols)))
        if m in (1, 7):
            maps += [(f"mois {m}, P95 brut - ERA5", raw[2]), (f"mois {m}, P95 corrige - ERA5", fix[2])]
        if v.trace is not None:
            extra.append((m, [100 * np.mean(a < v.trace) for a in (ref_v[mv == m], x, corr)]))
        elif v.bounds != (None, None):
            extra.append((m, [at_bound(a, v) for a in (ref_v[mv == m], x, corr)]))
    if v.trace is not None:
        print(f"\nJours secs (< {v.trace * scale:g} {unit}), en %, moyenne sur les mailles")
        print("mois | ERA5 | brut | corrige")
        for m, (e, r, c) in extra:
            print("%4d | %5.1f | %5.1f | %5.1f" % (m, e, r, c))
    elif extra:
        print(f"\nJours a une borne {v.bounds}, en %, ERA5 | brut | corrige")
        for m, (e, r, c) in extra:
            print("%4d | %s | %s | %s" % (m, *(" ".join("%5.1f" % s for s in a) for a in (e, r, c))))
    return maps


def change(fut, past, v):
    if v.kind == "add":
        return v.display[0] * (fut - past)
    ok = past > (v.trace or 0)
    return np.where(ok, 100 * (fut / np.where(ok, past, 1) - 1), np.nan)


def signal(name, cells):
    v = VARS[name]
    past, fut = range(1976, 2006), range(2071, 2101)
    unit = v.display[2].replace("°C", "K") if v.kind == "add" else "%"
    print(f"\nSignal 2071-2100 contre 1976-2005, moyenne sur les mailles, en {unit}")
    print("mois | moyenne brut/corrige (ecart max sur les mailles) | P95")
    # One 30-year series at a time: four of them would not fit in memory.
    s = {}
    for key, years in (("past", past), ("fut", fut)):
        for kind, read in (("raw", raw), ("cor", corrected)):
            x, mo = read(name, years, cells)
            s[kind, key] = [stats(x[mo == m]) for m in range(1, 13)]
            del x
    for m in range(1, 13):
        dr = change(s["raw", "fut"][m - 1], s["raw", "past"][m - 1], v)
        dc = change(s["cor", "fut"][m - 1], s["cor", "past"][m - 1], v)
        print("%4d | %6.2f/%6.2f (%5.2f) | %6.2f/%6.2f (%5.2f)" % (
            m, np.nanmean(dr[0]), np.nanmean(dc[0]), np.nanmax(np.abs(dc[0] - dr[0])),
            np.nanmean(dr[2]), np.nanmean(dc[2]), np.nanmax(np.abs(dc[2] - dr[2]))))


def main(argv):
    if len(argv) != 1 or argv[0] not in VARS:
        print(__doc__)
        return 1
    name = argv[0]
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    grid = model(name, 1970)[1]
    maps = split_sample(name, cells)
    signal(name, cells)

    top = np.nanpercentile(np.abs(np.concatenate([m for _, m in maps])), 98)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    for ax, (title, val) in zip(axes.flat, maps):
        full = np.full(keep.size, np.nan)
        full[cells] = val
        im = ax.pcolormesh(grid.longitude, grid.latitude, full.reshape(keep.shape),
                           cmap="RdBu_r", vmin=-top, vmax=top)
        ax.set_title(f"{title} ({VARS[name].display[2].replace('°C', 'K')}), 1988-2005")
    fig.colorbar(im, ax=axes, shrink=0.8)
    path = FIG / f"{name}_validation.png"
    fig.savefig(path, dpi=90)
    print("\ncartes :", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
