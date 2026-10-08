"""Checks of the QDM correction, printed and drawn in data/correction/.

    python -m src.correction.check tas

1. Split sample, CAL cut in two halves (qdm.HALVES; 1970-1987 and 1988-2005
   for RCA4): calibrate on the first, correct the second (its own years
   as the model distribution), compare with ERA5 on the second. Scores per month,
   over the cells, for the mean and the 5th and 95th percentiles, in the
   display unit of the variable. For precipitation, the dry-day frequency too;
   for bounded variables, the share of days at a bound. Derived variables
   (huss, rsus) are rebuilt from fields calibrated on CAL: their files
   are compared as they are, so the second half is not independent there.
   Then, on the same series, indices of what the app will show
   (hot days, frost days, dry spells, 5-day rainfall, day-to-day persistence),
   each computed year by year and averaged over the years.
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

from src.correction.qdm import CAL, DAY, HALVES, LABELS, OUT, TABLES, VARS, calibrate, correct, model, reference
from src.correction.remap import load_weights, target as remapped

FIG = TABLES


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
    cal, val = HALVES
    ref_c, mc = reference(name, cal, cells)
    ref_v, mv = reference(name, val, cells)
    hist_c, _ = raw(name, cal, cells)
    sim_v, _ = raw(name, val, cells)
    if v.derived:
        cor_v, _ = corrected(name, val, cells)
        print(f"Variable derivee, fichiers corriges (calibres {CAL[0]}-{CAL[1]}), {LABELS[1]}, ecart au ERA5 en {unit}")
    else:
        print(f"Validation croisee (calibre {LABELS[0]}, teste {LABELS[1]}), ecart au ERA5 en {unit}")
    print("mois | moyenne brut/corrige (biais moyen, RMS sur les mailles) | P5 | P95")
    maps, extra = [], []
    if not v.derived:
        cor_v = np.empty_like(sim_v)
    for m in range(1, 13):
        if v.derived:
            corr = cor_v[mv == m]
        else:
            x = sim_v[mv == m]
            corr = correct(x, x, calibrate(ref_c[mc == m], hist_c[mc == m], v), v)
            cor_v[mv == m] = corr
        x = sim_v[mv == m]
        e = stats(ref_v[mv == m])
        e_raw, e_fix = scale * (stats(x) - e), scale * (stats(corr) - e)
        cols = []
        for k in range(3):
            cols.append("%+6.2f/%+6.2f (%5.2f/%5.2f)" % (
                e_raw[k].mean(), e_fix[k].mean(), np.sqrt((e_raw[k] ** 2).mean()),
                np.sqrt((e_fix[k] ** 2).mean())))
        print("%4d | %s" % (m, " | ".join(cols)))
        if m in (1, 7):
            maps += [(f"mois {m}, P95 brut - ERA5", e_raw[2]), (f"mois {m}, P95 corrige - ERA5", e_fix[2])]
        if v.wet is not None:
            extra.append((m, [100 * np.mean(a < v.wet) for a in (ref_v[mv == m], x, corr)]))
        elif v.bounds != (None, None):
            extra.append((m, [at_bound(a, v) for a in (ref_v[mv == m], x, corr)]))
    if v.wet is not None:
        print(f"\nJours secs (< {v.wet * scale:g} {unit}), en %, moyenne sur les mailles")
        print("mois | ERA5 | brut | corrige")
        for m, (e, r, c) in extra:
            print("%4d | %5.1f | %5.1f | %5.1f" % (m, e, r, c))
    elif extra:
        print(f"\nJours a une borne {v.bounds}, en %, ERA5 | brut | corrige")
        for m, (e, r, c) in extra:
            print("%4d | %s | %s | %s" % (m, *(" ".join("%5.1f" % s for s in a) for a in (e, r, c))))
    del ref_c, hist_c
    yv = np.concatenate([np.full(366 if y % 4 == 0 else 365, y) for y in val])
    indices(name, {"ERA5": ref_v, "brut": sim_v, "corrige": cor_v}, yv, mv)
    return maps


def run_max(cond):
    """Longest run of True along days, per cell."""
    cur = np.zeros(cond.shape[1], "int32")
    best = cur.copy()
    for row in cond:
        cur = (cur + 1) * row
        np.maximum(best, cur, out=best)
    return best


def run_mean(cond):
    """Mean length of the runs of True, per cell (0 where there is none)."""
    starts = cond[0] + (cond[1:] & ~cond[:-1]).sum(0)
    return np.where(starts > 0, cond.sum(0) / np.maximum(starts, 1), 0)


def persistence(x, mo):
    """Correlation of each day's anomaly (to its calendar-month mean) with the next."""
    a = x.astype("float32")
    for m in range(1, 13):
        a[mo == m] -= a[mo == m].mean(0)
    a0, a1 = a[:-1], a[1:]
    return (a0 * a1).mean(0) / np.sqrt((a0 ** 2).mean(0) * (a1 ** 2).mean(0))


C0, MM = 273.15, 1 / DAY  # 0 degC in K, 1 mm/day in kg m-2 s-1
# name: [(label, function of one year (days, cells) to (cells,))]
INDICES = {
    "tasmax": [("jours Tx > 25 C (/an)", lambda x: (x > C0 + 25).sum(0)),
               ("jours Tx > 30 C (/an)", lambda x: (x > C0 + 30).sum(0)),
               ("Tx max de l'annee (C)", lambda x: x.max(0) - C0),
               ("plus longue serie Tx > 30 C (j)", lambda x: run_max(x > C0 + 30))],
    "tasmin": [("nuits tropicales Tn > 20 C (/an)", lambda x: (x > C0 + 20).sum(0)),
               ("jours de gel Tn < 0 C (/an)", lambda x: (x < C0).sum(0)),
               ("Tn min de l'annee (C)", lambda x: x.min(0) - C0),
               ("plus longue serie de gel (j)", lambda x: run_max(x < C0))],
    "pr": [("cumul annuel (mm)", lambda x: x.sum(0) * DAY),
           ("jours >= 1 mm (/an)", lambda x: (x >= MM).sum(0)),
           ("pluie max en 1 jour (mm)", lambda x: x.max(0) * DAY),
           ("pluie max en 5 jours (mm)",
            lambda x: np.lib.stride_tricks.sliding_window_view(x, 5, axis=0).sum(-1).max(0) * DAY),
           ("plus longue serie seche (j)", lambda x: run_max(x < MM)),
           ("duree moyenne des series seches (j)", lambda x: run_mean(x < MM))],
}


def indices(name, series, yv, mo):
    """Indices per year, averaged over the years, then compared over the cells."""
    rows = []
    for label, f in INDICES.get(name, []):
        val = {k: np.mean([f(x[yv == y]) for y in np.unique(yv)], axis=0) for k, x in series.items()}
        rows.append((label, val))
    rows.append(("persistance jour a jour", {k: persistence(x, mo) for k, x in series.items()}))
    print(f"\nIndices {LABELS[1]} (par an, moyennes sur les annees) : moyenne sur les mailles "
          "ERA5 | brut | corrige, puis RMS sur les mailles brut/corrige - ERA5")
    for label, val in rows:
        e = val["ERA5"]
        rms = [np.sqrt(np.nanmean((val[k] - e) ** 2)) for k in ("brut", "corrige")]
        print("%-38s %8.2f | %8.2f | %8.2f   (%6.2f/%6.2f)" % (
            label, np.nanmean(e), np.nanmean(val["brut"]), np.nanmean(val["corrige"]), *rms))


def change(fut, past, v):
    if v.kind == "add":
        return v.display[0] * (fut - past)
    ok = past > (v.wet or 0)
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
        ax.set_title(f"{title} ({VARS[name].display[2].replace('°C', 'K')}), {LABELS[1]}")
    fig.colorbar(im, ax=axes, shrink=0.8)
    path = FIG / f"{name}_validation.png"
    fig.savefig(path, dpi=90)
    print("\ncartes :", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
