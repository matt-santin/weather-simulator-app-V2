"""Distance between distributions and spatial coherence, raw and corrected CORDEX against ERA5.

    python -m src.correction.scores tas
    python -m src.correction.scores tas 44 48 4 10      only the cells in that box (lat, lon)

Both on the split sample of src.correction.check (qdm.HALVES; 1970-1987 and
1988-2005 for RCA4): the correction calibrated on the first half and applied
to the second, compared with ERA5 on the second (derived variables: their
final files, calibrated on CAL).

1. Distributions, per cell and calendar month. The Wasserstein distance
   W1 = mean over tau of |Q_A(tau) - Q_B(tau)|, the mean gap between quantiles
   of same rank, in the unit of the variable, for ERA5 against raw and
   against corrected. Its floor is W1 between ERA5 on the two halves:
   what two samples of the real climate already differ
   by (internal variability and trend). A correction cannot do better. For
   precipitation, the gap in wet-day frequency, then W1 on wet days only.
2. Spatial coherence, per season. Daily anomalies (to the mean of each cell
   and calendar month) are correlated in time between each cell and its
   neighbours LAGS cells away, east and north, then averaged over both
   directions. Each cell is corrected on its own: the correction may change
   how alike neighbouring cells are on a given day. For precipitation, the
   wet-day occurrence is correlated too.

Printed: medians over regions; drawn in data/correction/<variable>_scores.png.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import LogNorm

from src.config import ARCHIVE
from src.correction.check import corrected, raw
from src.correction.qdm import HALVES, LABELS, TABLES, VARS, calibrate, correct, quantiles, reference
from src.correction.remap import load_weights

CAL, VAL = HALVES
LAGS = (1, 2, 4, 8)  # in 0.25 deg cells, about 28, 56, 110, 220 km north-south
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}
MIN_WET = 30  # wet days in each sample, under which W1 on wet days is not computed


def cross_validation(name, cells):
    """ERA5 on CAL and VAL, raw and corrected CORDEX on VAL, (days, cells) each,
    with the months of CAL and VAL days."""
    v = VARS[name]
    ref_c, mc = reference(name, CAL, cells)
    ref_v, mv = reference(name, VAL, cells)
    sim_v, _ = raw(name, VAL, cells)
    if v.derived:
        cor_v, _ = corrected(name, VAL, cells)
    else:
        hist_c, _ = raw(name, CAL, cells)
        cor_v = np.empty_like(sim_v)
        for m in range(1, 13):
            x = sim_v[mv == m]
            cor_v[mv == m] = correct(x, x, calibrate(ref_c[mc == m], hist_c[mc == m], v, m), v)
        del hist_c
    return ref_c, mc, ref_v, mv, sim_v, cor_v


def w1(a, b):
    """Wasserstein distance between two samples, per cell, from their quantiles (NaN left out)."""
    return np.abs(quantiles(a) - quantiles(b)).mean(0)


def wet_only(x, wet):
    return np.where(x >= wet, x, np.nan)


def regions(cells):
    lsm = xr.open_dataarray(ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc")
    lat = np.repeat(lsm.latitude.values, lsm.longitude.size)[cells]
    lon = np.tile(lsm.longitude.values, lsm.latitude.size)[cells]
    land = lsm.values.ravel()[cells] >= 0.5
    europe = (lat >= 35) & (lon >= -10) & (lon <= 40)
    return {"Europe terre": europe & land, "Europe mer": europe & ~land,
            "nord de 60 N": lat >= 60, "sud de 35 N": lat < 35}


def distributions(name, data, reg):
    v = VARS[name]
    scale, unit = v.display[0], v.display[2].replace("°C", "K")
    ref_c, mc, ref_v, mv, sim_v, cor_v = data
    out = {}
    for m in range(1, 13):
        a_c, a_v, s, c = ref_c[mc == m], ref_v[mv == m], sim_v[mv == m], cor_v[mv == m]
        res = {}
        if v.wet is not None:
            res["freq"] = [100 * ((x >= v.wet).mean(0) - (a_v >= v.wet).mean(0)) for x in (a_c, s, c)]
            n = [(x >= v.wet).sum(0) for x in (a_c, a_v, s, c)]
            ok = np.min(n, axis=0) >= MIN_WET
            a_c, a_v, s, c = (wet_only(x, v.wet) for x in (a_c, a_v, s, c))
        else:
            ok = np.ones(a_v.shape[1], bool)
        res["w1"] = [np.where(ok, scale * w1(a_v, x), np.nan) for x in (a_c, s, c)]  # floor, raw, corrected
        out[m] = res

    what = f"W1{' sur les jours de pluie' if v.wet is not None else ''}, en {unit}"
    print(f"1. Distributions, {LABELS[1]} contre ERA5 {LABELS[1]} (correction calibree sur {LABELS[0]})")
    print(f"   {what}, mediane sur les mailles : plancher (ERA5 {LABELS[0]}) | brut | corrige ;"
          " part des mailles au plancher (W1 <= plancher) : brut | corrige")
    for r, mask in reg.items():
        print(f"\n   {r} ({mask.sum()} mailles)")
        print("   mois | plancher |   brut | corrige | au plancher brut | corrige")
        for m in range(1, 13):
            f, b, c = (x[mask] for x in out[m]["w1"])
            ok = np.isfinite(f)
            if not ok.any():
                continue
            print("   %4d | %8.3f | %6.3f | %7.3f | %9.0f %% | %5.0f %%" % (
                m, np.median(f[ok]), np.median(b[ok]), np.median(c[ok]),
                100 * np.mean(b[ok] <= f[ok]), 100 * np.mean(c[ok] <= f[ok])))
    if v.wet is not None:
        print(f"\n   Frequence des jours de pluie (>= 1 mm), ecart a ERA5 {LABELS[1]} en points, "
              "mediane des valeurs absolues : plancher | brut | corrige")
        for r, mask in reg.items():
            print(f"   {r:14s} " + " ".join(
                "%2d:%4.1f/%4.1f/%4.1f" % (m, *(np.median(np.abs(x[mask])) for x in out[m]["freq"]))
                for m in (1, 4, 7, 10)))
    return out


def grid_of(cells, shape):
    """Row and column of each cell, in the smallest box holding them."""
    iy, ix = np.divmod(cells, shape[1])
    return iy - iy.min(), ix - ix.min(), (iy.max() - iy.min() + 1, ix.max() - ix.min() + 1)


def neighbour_corr(x, iy, ix, box, lag):
    """Correlation in time of each cell with its neighbour lag cells east and north,
    averaged over both, (cells,); x is (days, cells) of anomalies."""
    g = np.full((x.shape[0], *box), np.nan, "float32")
    g[:, iy, ix] = x
    res = []
    for sl_a, sl_b in (((slice(None), slice(None, -lag)), (slice(None), slice(lag, None))),
                       ((slice(None, -lag), slice(None)), (slice(lag, None), slice(None)))):
        a, b = g[(slice(None), *sl_a)], g[(slice(None), *sl_b)]
        r = (a * b).sum(0) / np.sqrt((a * a).sum(0) * (b * b).sum(0))
        full = np.full(box, np.nan, "float32")
        full[sl_a] = r
        res.append(full[iy, ix])
    return np.nanmean(res, axis=0)


def anomalies(x, mo):
    a = x.astype("float32")
    for m in np.unique(mo):
        a[mo == m] -= a[mo == m].mean(0)
    return a


def spatial(name, data, cells, shape, reg):
    v = VARS[name]
    _, _, ref_v, mv, sim_v, cor_v = data
    iy, ix, box = grid_of(cells, shape)
    kinds = [("anomalies", lambda x, mo: anomalies(x, mo))]
    if v.wet is not None:
        kinds.append(("occurrence", lambda x, mo: anomalies((x >= v.wet).astype("float32"), mo)))
    out = {}
    for kind, f in kinds:
        print(f"\n2. Coherence spatiale ({kind}), {LABELS[1]} : correlation avec les voisines a "
              f"{', '.join(str(k) for k in LAGS)} mailles, mediane sur les mailles, ERA5 / brut / corrige")
        for s, months in SEASONS.items():
            sel = np.isin(mv, months)
            r = {k: [neighbour_corr(f(x[sel], mv[sel]), iy, ix, box, k) for x in (ref_v, sim_v, cor_v)]
                 for k in LAGS}
            out[kind, s] = r
            for rg, mask in reg.items():
                if not mask.any():
                    continue
                print(f"   {s} {rg:14s} " + " | ".join(
                    "%d: %.2f/%.2f/%.2f" % (k, *(np.nanmedian(c[mask]) for c in r[k])) for k in LAGS))
    return out


def draw(name, cells, keep, dist, spat):
    v = VARS[name]
    lsm = xr.open_dataarray(ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc")

    def grid(val):
        full = np.full(keep.size, np.nan)
        full[cells] = val
        return full.reshape(keep.shape)

    fig, axes = plt.subplots(2, 4, figsize=(20, 9), constrained_layout=True)
    for i, m in enumerate((1, 7)):
        f, b, c = dist[m]["w1"]
        for j, (title, val) in enumerate((("brut / plancher", b / f), ("corrige / plancher", c / f))):
            im = axes[i, j].pcolormesh(lsm.longitude, lsm.latitude, grid(val), cmap="RdBu_r",
                                       norm=LogNorm(0.25, 4))
            axes[i, j].set_title(f"mois {m}, W1 {title}")
        kind = "anomalies"
        s = "DJF" if m == 1 else "JJA"
        e, r, c = spat[kind, s][1]
        for j, (title, val) in enumerate((("brut - ERA5", r - e), ("corrige - ERA5", c - e)), start=2):
            im2 = axes[i, j].pcolormesh(lsm.longitude, lsm.latitude, grid(val), cmap="PuOr",
                                        vmin=-0.2, vmax=0.2)
            axes[i, j].set_title(f"{s}, correlation avec la voisine, {title}")
    fig.colorbar(im, ax=axes[:, :2], shrink=0.6, label="rapport au plancher (rouge : au-dessus)")
    fig.colorbar(im2, ax=axes[:, 2:], shrink=0.6, label="ecart de correlation")
    fig.suptitle(f"{name} : distance aux distributions et coherence spatiale, {LABELS[1]}")
    TABLES.mkdir(parents=True, exist_ok=True)
    path = TABLES / f"{name}_scores.png"
    fig.savefig(path, dpi=80)
    print("\ncartes :", path)


def main(argv):
    if len(argv) not in (1, 5) or argv[0] not in VARS:
        print(__doc__)
        return 1
    name = argv[0]
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    if len(argv) == 5:
        la0, la1, lo0, lo1 = map(float, argv[1:])
        lsm = xr.open_dataarray(ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc")
        lat = np.repeat(lsm.latitude.values, lsm.longitude.size)[cells]
        lon = np.tile(lsm.longitude.values, lsm.latitude.size)[cells]
        cells = cells[(lat >= la0) & (lat <= la1) & (lon >= lo0) & (lon <= lo1)]
    reg = regions(cells)
    data = cross_validation(name, cells)
    dist = distributions(name, data, reg)
    spat = spatial(name, data, cells, keep.shape, reg)
    draw(name, cells, keep, dist, spat)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
