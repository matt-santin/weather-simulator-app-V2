"""CORDEX, raw and corrected, and ERA5 against E-OBS, the gridded station analysis.

    python -m src.correction.eobs tasmax

Only distributions are compared, per ERA5 cell and calendar month: CORDEX does
not follow the real weather day by day.

A. 1970-2005 (sfcWind: 1980-2005, fg starts in 1980): ERA5, raw and corrected
   against E-OBS. Corrected files are the production ones, calibrated on these
   years, so corrected is close to ERA5 by construction: A says how far ERA5,
   the target of the correction, is from the stations. Floor: E-OBS first half
   of A against the other, what two samples of the real climate differ by
   (see below).
B. 2006-2024: raw and corrected against E-OBS, years the correction never saw.
   No ERA5 there, and no clean floor. A gap in B mixes the error of the
   correction, the error of the model trend, the ERA5 to E-OBS gap (read in A)
   and 19 years of internal variability.
Floor: the years of A drawn at random into two halves (fixed seed, so the same
draw each run), E-OBS of one half against the other. Drawn rather than split
in time, so that the warming within A does not count as a gap.

E-OBS (0.25 deg, centres at x.125) is brought to the ERA5 grid (centres at
x.0, x.25): each ERA5 cell gets the mean of the 4 E-OBS cells around it, if at
least MIN_NEIGH of them are valid that day. On days E-OBS misses a cell, ERA5
and CORDEX of the same date are left out too, so that all samples cover the
same years. A cell counts for a month if E-OBS holds MIN_VALID of its days.

Per cell and month, in the display unit: bias of the mean, of P5 and of P95
(model minus E-OBS) and W1, the mean gap between quantiles of same rank. For
precipitation: wet-day (>= 1 mm) frequency gap in points, bias of the mean in
%, W1 on wet days, and drizzle (0.1 to 1 mm) frequency and share of the total.

Results over Europe land and north of 60 N, then, for Europe land, over the
cells where E-OBS is most reliable: low ensemble spread (tx, tn, rr: the half
of the cells with the lowest). Left out: sea (a few coastal cells, estimated
from land stations) and south of 35 N (few stations, a network that changes
between A and B: tasmax of July cools by 3.5 K on the cells common to both).

Printed; maps of the bias of the mean, January and July, in
data/correction/<variable>_eobs.png.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from src.config import EOBS, ERA5
from src.correction.qdm import ERA5_DAILY, OUT, TABLES, VARS, quantiles
from src.correction.remap import load_weights, target as remapped
from src.correction.scores import regions
from src.download.eobs import MEAN, VERSION

NAMES = {cordex: e for e, cordex in MEAN.items()}  # CORDEX name: E-OBS name
SPREAD = {"tasmax", "tasmin", "pr"}
B = range(2006, 2025)
MIN_NEIGH = 3  # valid E-OBS cells out of the 4 around an ERA5 cell
MIN_VALID = 0.8  # share of the days of a month E-OBS must hold in a cell
WET, DRIZZLE = 1.0, 0.1  # mm/day
MIN_WET = 30  # wet days in each sample, under which W1 on wet days is not computed
REGIONS = ("Europe terre", "nord de 60 N")
SEED = 0


def period_a(name):
    return range(1980 if name == "sfcWind" else 1970, 2006)


def eobs_path(e, kind="mean"):
    return EOBS / f"{e}_ens_{kind}_0.25deg_reg_{VERSION}.nc"


# --- grids -----------------------------------------------------------------

def era5_grid():
    z = xr.open_dataarray(ERA5 / "fixed" / "z_ERA5.nc")
    return z.latitude.values, z.longitude.values


def neighbours(lat, lon, cells):
    """Row and column in the E-OBS grid of the 4 cells around each ERA5 cell, (4, cells)."""
    e = xr.open_dataset(EOBS / f"elev_ens_0.25deg_reg_{VERSION}.nc")
    elat, elon = e.latitude.values, e.longitude.values
    la = np.repeat(lat, lon.size)[cells]
    lo = np.tile(lon, lat.size)[cells]
    j0 = np.rint((la - 0.125 - elat[0]) / 0.25).astype(int)
    i0 = np.rint((lo - 0.125 - elon[0]) / 0.25).astype(int)
    J = np.stack([j0, j0, j0 + 1, j0 + 1])
    I = np.stack([i0, i0 + 1, i0, i0 + 1])
    inside = (J.min(0) >= 0) & (J.max(0) < elat.size) & (I.min(0) >= 0) & (I.max(0) < elon.size)
    return np.clip(J, 0, elat.size - 1), np.clip(I, 0, elon.size - 1), inside, elat, elon


def interpolate(field, J, I):
    """(days, lat, lon) E-OBS to (days, cells): mean of the valid neighbours, NaN under MIN_NEIGH."""
    x = field[:, J, I]  # (days, 4, cells)
    n = np.isfinite(x).sum(1)
    s = np.nansum(x, 1)
    return np.where(n >= MIN_NEIGH, s / np.maximum(n, 1), np.nan).astype("float32")


def setup():
    """ERA5 cells kept for the comparison (inside E-OBS, over its land) and their E-OBS neighbours."""
    lat, lon = era5_grid()
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    J, I, inside, elat, elon = neighbours(lat, lon, cells)
    elev = xr.open_dataarray(EOBS / f"elev_ens_0.25deg_reg_{VERSION}.nc").values[None]
    ze = interpolate(elev, J, I)[0]
    ok = inside & np.isfinite(ze)
    return lat, lon, cells[ok], J[:, ok], I[:, ok]


# --- reading, in the display unit, with the dates ----------------------------

def to_display(name, x):
    scale, offset, _ = VARS[name].display
    return (x * scale + offset).astype("float32")


def read_eobs(name, years, J, I, kind="mean"):
    da = xr.open_dataset(eobs_path(NAMES[name], kind))[NAMES[name]]
    da = da.sel(time=slice(f"{years[0]}-01-01", f"{years[-1]}-12-31"))
    xs = [interpolate(da.sel(time=str(y)).values, J, I) for y in years]
    return np.concatenate(xs), da.time.values.astype("datetime64[D]")


def read_era5(name, years, cells):
    v = VARS[name]
    xs, ds = [], []
    for y in years:
        das = [xr.open_dataset(ERA5_DAILY / f"{f}_ERA5_day_{y}0101-{y}1231.nc")[f] for f in v.era5]
        xs.append(v.convert(*[d.values.reshape(d.shape[0], -1)[:, cells] for d in das]))
        ds.append(das[0].time.values.astype("datetime64[D]"))
    return to_display(name, np.concatenate(xs)), np.concatenate(ds)


def read_cordex(name, years, cells, corrected):
    xs, ds = [], []
    for y in years:
        path = OUT / remapped(name, y).name if corrected else remapped(name, y)
        da = xr.open_dataset(path)[name]
        xs.append(da.values.reshape(da.shape[0], -1)[:, cells])
        ds.append(da.time.values.astype("datetime64[D]"))
    return to_display(name, np.concatenate(xs)), np.concatenate(ds)


def mask_like(x, dates, ref, ref_dates):
    """NaN in x wherever E-OBS misses the same date and cell."""
    i = np.searchsorted(ref_dates, dates)
    found = (i < ref_dates.size) & (ref_dates[np.minimum(i, ref_dates.size - 1)] == dates)
    miss = np.zeros(x.shape, bool)
    miss[found] = np.isnan(ref[i[found]])
    x[miss] = np.nan
    return x


def month(dates):
    return dates.astype("datetime64[M]").astype(int) % 12 + 1


# --- scores ------------------------------------------------------------------

def summary(x):
    """Per cell: mean, P5, P95 and the quantiles, NaN left out."""
    q = quantiles(x)
    return {"mean": np.nanmean(x, 0), "p5": q[4:6].mean(0), "p95": q[94:96].mean(0), "q": q}


def wet_summary(x):
    valid = np.isfinite(x)
    n = np.maximum(valid.sum(0), 1)
    wet = np.where(valid, x >= WET, False)
    drz = np.where(valid, (x >= DRIZZLE) & (x < WET), False)
    total = np.nansum(x, 0)
    return {"mean": np.nanmean(x, 0), "freq": 100 * wet.sum(0) / n, "drizzle": 100 * drz.sum(0) / n,
            "drizzle_share": 100 * np.nansum(np.where(drz, x, 0), 0) / np.where(total > 0, total, np.nan),
            "nwet": wet.sum(0), "q": quantiles(np.where(wet, x, np.nan))}


def compare(name, e, others):
    """Scores of each sample against E-OBS, for one month: dict of name: dict of score: (cells,)."""
    pr = VARS[name].wet is not None
    f = wet_summary if pr else summary
    se = f(e)
    out = {}
    for k, x in others.items():
        s = f(x)
        if pr:
            ok = np.minimum(se["nwet"], s["nwet"]) >= MIN_WET
            out[k] = {"freq": s["freq"] - se["freq"],
                      "mean": 100 * (s["mean"] / np.where(se["mean"] > 0, se["mean"], np.nan) - 1),
                      "w1": np.where(ok, np.abs(s["q"] - se["q"]).mean(0), np.nan),
                      "drizzle": s["drizzle"], "drizzle_share": s["drizzle_share"]}
        else:
            out[k] = {"mean": s["mean"] - se["mean"], "p5": s["p5"] - se["p5"],
                      "p95": s["p95"] - se["p95"], "w1": np.abs(s["q"] - se["q"]).mean(0)}
    if pr:
        out["E-OBS"] = {"drizzle": se["drizzle"], "drizzle_share": se["drizzle_share"]}
    return out


def run_period(name, years, cells, J, I, with_era5):
    """Scores per month for a period: {month: {sample: {score: (cells,)}}}."""
    e, de = read_eobs(name, years, J, I)
    samples = {}
    if with_era5:
        samples["ERA5"] = read_era5(name, years, cells)
    samples["brut"] = read_cordex(name, years, cells, corrected=False)
    samples["corrige"] = read_cordex(name, years, cells, corrected=True)
    samples = {k: (mask_like(x, d, e, de), d) for k, (x, d) in samples.items()}
    me = month(de)
    drawn = np.random.default_rng(SEED).choice(list(years), len(years) // 2, replace=False)
    res = {}
    for m in range(1, 13):
        em = e[me == m]
        valid = np.isfinite(em).mean(0) >= MIN_VALID
        others = {k: x[month(d) == m] for k, (x, d) in samples.items()}
        if with_era5:
            # Floor: E-OBS of half of the years, drawn at random, against the other half.
            yr = de[me == m].astype("datetime64[Y]").astype(int) + 1970
            half = np.isin(yr, drawn)
            floor = compare(name, em[~half], {"plancher": em[half]})["plancher"]
        r = compare(name, em, others)
        if with_era5:
            r["plancher"] = floor
        for k in r:
            for s in r[k]:
                r[k][s] = np.where(valid, r[k][s], np.nan)
        res[m] = r
    del e, samples
    return res


def reliability(name, years, J, I):
    """Subsets of cells where E-OBS is most trusted, as boolean masks."""
    out = {}
    if name in SPREAD:
        sp, _ = read_eobs(name, years, J, I, kind="spread")
        s = np.nanmean(sp, 0)
        if name == "pr":
            mean, _ = read_eobs(name, years, J, I)
            s = s / np.nanmean(mean, 0)
        out["dispersion faible"] = s <= np.nanmedian(s)
    return out


# --- printing ----------------------------------------------------------------

def agg(x, how):
    x = x[np.isfinite(x)]
    if not x.size:
        return np.nan
    return {"moy": x.mean(), "rms": np.sqrt((x * x).mean()), "med": np.median(x)}[how]


def table(name, A, Bres, mask, title):
    unit = VARS[name].display[2].replace("°C", "K")
    n = int(mask.sum())
    key = "mean" if VARS[name].wet is None else "freq"
    va = [int((mask & np.isfinite(A[m]["corrige"][key])).sum()) for m in range(1, 13)]
    vb = [int((mask & np.isfinite(Bres[m]["corrige"][key])).sum()) for m in range(1, 13)]
    print(f"\n  {title} ({n} mailles, valides selon le mois : A {min(va)} a {max(va)}, B {min(vb)} a {max(vb)})")
    if not n:
        return
    if VARS[name].wet is not None:
        print("  mois | frequence pluie, ecart en pts  A: ERA5 brut corr | B: brut corr"
              " | cumul, ecart en %  A: ERA5 brut corr | B: brut corr"
              " | W1 jours de pluie, mm  A: plancher ERA5 brut corr | B: brut corr")
        for m in range(1, 13):
            a, b = A[m], Bres[m]
            row = [agg(a[k]["freq"][mask], "med") for k in ("ERA5", "brut", "corrige")]
            row += [agg(b[k]["freq"][mask], "med") for k in ("brut", "corrige")]
            row += [agg(a[k]["mean"][mask], "med") for k in ("ERA5", "brut", "corrige")]
            row += [agg(b[k]["mean"][mask], "med") for k in ("brut", "corrige")]
            row += [agg(a[k]["w1"][mask], "med") for k in ("plancher", "ERA5", "brut", "corrige")]
            row += [agg(b[k]["w1"][mask], "med") for k in ("brut", "corrige")]
            print("  %4d | " % m + "%+5.1f %+5.1f %+5.1f | %+5.1f %+5.1f | " % tuple(row[:5])
                  + "%+5.0f %+5.0f %+5.0f | %+5.0f %+5.0f | " % tuple(row[5:10])
                  + "%5.2f %5.2f %5.2f %5.2f | %5.2f %5.2f" % tuple(row[10:]))
        print("  (medianes sur les mailles)")
        print("  bruine (0,1 a 1 mm), A : frequence en % des jours, E-OBS / ERA5 / corrige ;"
              " part du cumul en %, E-OBS / ERA5 / corrige")
        for m in range(1, 13):
            a = A[m]
            f = [agg(a[k]["drizzle"][mask], "med") for k in ("E-OBS", "ERA5", "corrige")]
            s = [agg(a[k]["drizzle_share"][mask], "med") for k in ("E-OBS", "ERA5", "corrige")]
            print("  %4d | %5.1f %5.1f %5.1f | %5.1f %5.1f %5.1f" % (m, *f, *s))
        return
    print(f"  mois | biais de la moyenne en {unit}, moyenne (RMS) sur les mailles"
          "  A: ERA5 brut corr | B: brut corr"
          f" | W1 en {unit}, mediane  A: plancher ERA5 brut corr | B: brut corr")
    for m in range(1, 13):
        a, b = A[m], Bres[m]
        cells = []
        for r, k in [(a, "ERA5"), (a, "brut"), (a, "corrige"), (b, "brut"), (b, "corrige")]:
            x = r[k]["mean"][mask]
            cells.append("%+5.2f (%4.2f)" % (agg(x, "moy"), agg(x, "rms")))
        w = [agg(a[k]["w1"][mask], "med") for k in ("plancher", "ERA5", "brut", "corrige")]
        w += [agg(b[k]["w1"][mask], "med") for k in ("brut", "corrige")]
        print("  %4d | %s | %s | %5.2f %5.2f %5.2f %5.2f | %5.2f %5.2f" % (
            m, " ".join(cells[:3]), " ".join(cells[3:]), *w))
    print(f"  mois | biais P5 et P95 en {unit}, moyenne sur les mailles"
          "  A: ERA5 corr | B: brut corr (P5) || idem (P95)")
    for m in range(1, 13):
        a, b = A[m], Bres[m]
        row = []
        for p in ("p5", "p95"):
            row += [agg(a[k][p][mask], "moy") for k in ("ERA5", "corrige")]
            row += [agg(b[k][p][mask], "moy") for k in ("brut", "corrige")]
        print("  %4d | %+5.2f %+5.2f | %+5.2f %+5.2f || %+5.2f %+5.2f | %+5.2f %+5.2f" % (m, *row))


def draw(name, lat, lon, cells, A, Bres):
    unit = VARS[name].display[2].replace("°C", "K")
    pr = VARS[name].wet is not None
    lim = 50 if pr else 3

    def grid(val):
        full = np.full(lat.size * lon.size, np.nan)
        full[cells] = val
        return full.reshape(lat.size, lon.size)

    panels = [("A", "ERA5"), ("A", "brut"), ("A", "corrige"), ("B", "brut"), ("B", "corrige")]
    fig, axes = plt.subplots(2, 5, figsize=(25, 9), constrained_layout=True)
    for i, m in enumerate((1, 7)):
        for j, (p, k) in enumerate(panels):
            r = (A if p == "A" else Bres)[m]
            im = axes[i, j].pcolormesh(lon, lat, grid(r[k]["mean"]), cmap="RdBu_r", vmin=-lim, vmax=lim)
            axes[i, j].set_title(f"mois {m}, {p}, {k} - E-OBS")
            axes[i, j].set_xlim(-25, 45)
            axes[i, j].set_ylim(30, 72)
    fig.colorbar(im, ax=axes, shrink=0.6, label=f"biais de la moyenne ({'%' if pr else unit})")
    fig.suptitle(f"{name} contre E-OBS {VERSION} : A = 1970-2005, B = 2006-2024")
    path = TABLES / f"{name}_eobs.png"
    fig.savefig(path, dpi=80)
    print("\ncartes :", path)


def main(argv):
    if len(argv) != 1 or argv[0] not in NAMES:
        print(__doc__)
        return 1
    name = argv[0]
    lat, lon, cells, J, I = setup()
    a = period_a(name)
    A = run_period(name, a, cells, J, I, with_era5=True)
    Bres = run_period(name, B, cells, J, I, with_era5=False)
    reg = regions(cells)
    print(f"{name} contre E-OBS {VERSION}, A = {a[0]}-{a[-1]}, B = {B[0]}-{B[-1]} ; "
          "ecarts = modele moins E-OBS")
    for r in REGIONS:
        table(name, A, Bres, reg[r], r)
    for s, mask in reliability(name, a, J, I).items():
        table(name, A, Bres, reg["Europe terre"] & mask, f"Europe terre, {s}")
    draw(name, lat, lon, cells, A, Bres)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
