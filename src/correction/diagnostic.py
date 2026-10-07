"""Diagnosis of a raw CORDEX run, before any correction.

    WSA_MODEL=mpi python -m src.correction.diagnostic bias tas      0.25 deg, against ERA5
    WSA_MODEL=mpi python -m src.correction.diagnostic land tasmax   0.1 deg, against ERA5-Land
    WSA_MODEL=mpi python -m src.correction.diagnostic step          jump at the scenario start

Run from the repo root, after src.correction.remap (and land remap for the
0.1 deg grid), with the external drive plugged in. Output in
data/correction/<run>/diagnostic/.

bias, land: per cell and calendar month, over PERIOD (1970 to the last
historical year of the run, the span where the model has the observed
forcing), mean, P5 and P95 of the model and of the reference. Bias = model
minus reference, in the display unit; for the multiplicative variables (pr,
sfcWind, rsds, rsus, huss), the means and P95 are compared as a ratio, in %.
For pr, the share of wet days (>= 1 mm) too, in points. Printed per month and
region: bias averaged over the cells, and RMS between cells. Maps of the bias
of the mean for January, April, July and October.
For temperatures, the cold-tail criterion of docs/correction.md (section 5):
cells where, for at least one month, the P5 is more than 10 K too cold and
its bias is more than 7 K below that of the P95 (snow or ice the reference
does not have).

step: the scenario forcing starts in the year after the historical one, and
ICON-CLM-202407-1-1 has a known aerosol fault in its scenarios
(zenodo 19812905, optical depth about 50 % too high, a constant offset). For
each variable, yearly means over STEP_YEARS, per region and season, are fitted
by a line plus a step at the first scenario year; the step is printed with
twice its standard error and the year-to-year spread around the fit.
"""

import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from src.config import ARCHIVE, DATA
from src.correction import land
from src.correction.models import MODEL
from src.correction.qdm import VARS, model, reference
from src.correction.remap import load_weights, target as remapped

PERIOD = (1970, MODEL.hist_end)
STEP_YEARS = range(MODEL.hist_end - 19, MODEL.hist_end + 21)
OUT = DATA / "correction" / MODEL.tables / "diagnostic"
LSM = ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc"
MAP_MONTHS = (1, 4, 7, 10)
SEASONS = {"annee": range(1, 13), "DJF": (12, 1, 2), "JJA": (6, 7, 8)}
NAMES = ("tas", "tasmax", "tasmin", "pr", "hurs", "huss", "clt", "sfcWind", "rsds", "rlds",
         "rsus", "alb", "ps", "evspsbl", "zg500")


def regions(lat, lon, is_land):
    europe = (lat >= 35) & (lon >= -10) & (lon <= 40)
    return {"Europe terre": europe & is_land,
            "France (42-51 N, 5 W-8 E)": (lat >= 42) & (lat <= 51) & (lon >= -5) & (lon <= 8) & is_land,
            "nord de 60 N": lat >= 60, "sud de 35 N": lat < 35}


def grid_025(cells):
    lsm = xr.open_dataarray(LSM)
    lat = np.repeat(lsm.latitude.values, lsm.longitude.size)[cells]
    lon = np.tile(lsm.longitude.values, lsm.latitude.size)[cells]
    return lat, lon, lsm.values.ravel()[cells], lsm.latitude.values, lsm.longitude.values


def grid_010(cells):
    g = xr.open_dataset(land.GRID)
    lat = np.repeat(g.latitude.values, g.longitude.size)[cells]
    lon = np.tile(g.longitude.values, g.latitude.size)[cells]
    return lat, lon, np.ones(cells.size), g.latitude.values, g.longitude.values


# --- bias --------------------------------------------------------------------


def collect(name, ncells, read_model, read_ref, tag):
    """Per month, stats of the model and the reference over PERIOD:
    {stat: (2, 12, cells)}, model first. Both series go through memmaps on the Mac."""
    v = VARS[name]
    years = range(PERIOD[0], PERIOD[1] + 1)
    days = np.arange(f"{PERIOD[0]}-01-01", f"{PERIOD[1] + 1}-01-01", dtype="datetime64[D]")
    year = days.astype("datetime64[Y]").astype(int) + 1970
    month = days.astype("datetime64[M]").astype(int) % 12 + 1
    OUT.mkdir(parents=True, exist_ok=True)
    packs = [np.lib.format.open_memmap(OUT / f"_{tag}_{name}_{k}.tmp", mode="w+",
                                       dtype="float32", shape=(days.size, ncells))
             for k in ("model", "ref")]
    t0 = time.time()
    for y in years:
        now = year == y
        for p, read in zip(packs, (read_model, read_ref)):
            x = read(y)
            if x.shape[0] != now.sum():
                raise ValueError(f"{name} {y} : {x.shape[0]} jours, {now.sum()} attendus")
            p[now] = x
    print(f"{name} : {PERIOD[0]}-{PERIOD[1]} lu en {time.time() - t0:.0f} s", flush=True)

    keys = ("mean", "p5", "p95") + (("wet",) if v.wet else ())
    out = {k: np.full((2, 12, ncells), np.nan, "float32") for k in keys}
    for m in range(1, 13):
        rows = np.flatnonzero(month == m)
        for s, p in enumerate(packs):
            x = np.asarray(p[rows])
            out["mean"][s, m - 1] = x.mean(0)
            out["p5"][s, m - 1], out["p95"][s, m - 1] = np.percentile(x, [5, 95], axis=0)
            if v.wet:
                out["wet"][s, m - 1] = 100 * (x >= v.wet).mean(0)
    paths = [Path(p.filename) for p in packs]
    del packs, p, x
    for path in paths:
        path.unlink()
    return out


def bias(name, st):
    """Model against reference, per stat: (12, cells), in the display unit or %."""
    v = VARS[name]
    scale = v.display[0]
    out = {}
    for k, (m, r) in ((k, st[k]) for k in st):
        if k == "wet":
            out[k] = m - r
        elif v.kind == "mul" and k != "p5":
            out[k] = 100 * (m / np.where(r > 0, r, np.nan) - 1)
        elif v.kind == "mul":
            continue  # P5 of a positive variable, often 0: not compared
        else:
            out[k] = scale * (m - r)
    return out


def unit(name, k):
    v = VARS[name]
    if k == "wet":
        return "points"
    if v.kind == "mul":
        return "%"
    return v.display[2].replace("°C", "K")


def report(name, b, lat, lon, is_land, tag):
    print(f"\n{name}, {MODEL.key}, brut contre {'ERA5-Land' if tag == 'land' else 'ERA5'}, "
          f"{PERIOD[0]}-{PERIOD[1]}, modele moins reference")
    for k, x in b.items():
        what = {"mean": "moyenne", "p5": "P5", "p95": "P95", "wet": "part de jours >= 1 mm"}[k]
        print(f"\n  {what} ({unit(name, k)}) : biais moyen sur les mailles / RMS entre mailles")
        regs = regions(lat, lon, is_land)
        print("  mois | " + " | ".join(regs))
        for m in range(12):
            cols = []
            for r in regs.values():
                y = x[m, r]
                y = y[np.isfinite(y)]
                cols.append(f"{y.mean():+7.2f} / {np.sqrt((y ** 2).mean()):6.2f}" if y.size else "")
            print(f"  {m + 1:4d} | " + " | ".join(cols))


def cold_tail(b, lat, is_land):
    """Cells where, for at least one month, P5 bias < -10 K and P95 bias - P5 bias > 7 K."""
    hit = ((b["p5"] < -10) & (b["p95"] - b["p5"] > 7)).any(0)
    print(f"\n  queue froide (P5 trop froid de plus de 10 K, et plus de 7 K de plus que le P95, "
          f"au moins un mois) : {hit.sum()} mailles sur {hit.size}")
    if is_land.dtype != bool:  # 0.25 deg: ERA5 land fraction
        cls = {"mer (lsm < 0,5)": is_land < 0.5, "cotes (0,5 a 0,9)": (is_land >= 0.5) & (is_land < 0.9),
               "terre (>= 0,9)": is_land >= 0.9}
        print("  " + ", ".join(f"{k} {(hit & c).sum()}" for k, c in cls.items()))
    print(f"  dont nord de 60 N : {(hit & (lat >= 60)).sum()}")
    return hit


def draw(name, b, cells, lats, lons, tag):
    x = b["mean"]
    lim = np.nanpercentile(np.abs(x), 98)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for ax, m in zip(axes.ravel(), MAP_MONTHS):
        field = np.full(lats.size * lons.size, np.nan, "float32")
        field[cells] = x[m - 1]
        im = ax.pcolormesh(lons, lats, field.reshape(lats.size, lons.size), cmap="RdBu_r",
                           vmin=-lim, vmax=lim, shading="nearest", rasterized=True)
        ax.set_title(f"mois {m}")
        ax.set_aspect(1.5)
    fig.colorbar(im, ax=axes, shrink=0.8, label=f"biais de la moyenne ({unit(name, 'mean')})")
    fig.suptitle(f"{name}, {MODEL.key} brut moins {'ERA5-Land' if tag == 'land' else 'ERA5'}, "
                 f"{PERIOD[0]}-{PERIOD[1]}")
    fig.savefig(OUT / f"{name}_{tag}_biais.png", dpi=110)
    plt.close(fig)


def save(name, st, cells, tag):
    xr.Dataset({k: (("source", "month", "cell"), a) for k, a in st.items()},
               coords={"source": ["model", "ref"], "month": np.arange(1, 13), "cell": cells},
               attrs={"period": f"{PERIOD[0]}-{PERIOD[1]}", "run": MODEL.key,
                      "grid": "ERA5-Land 0.1 deg" if tag == "land" else "ERA5 0.25 deg",
                      "cell": "flat index into (latitude, longitude)"}
               ).to_netcdf(OUT / f"{name}_{tag}_stats.nc")


def run_bias(name):
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    st = collect(name, cells.size, lambda y: model(name, y)[0][:, cells],
                 lambda y: reference(name, [y], cells)[0], "025")
    save(name, st, cells, "025")
    lat, lon, lsm, lats, lons = grid_025(cells)
    b = bias(name, st)
    report(name, b, lat, lon, lsm >= 0.5, "025")
    if name in land.REFERENCE:
        cold_tail(b, lat, lsm)
    draw(name, b, cells, lats, lons, "025")


def run_land(name):
    v = land.VARS[name]
    _, keep = land.load_weights()
    cells = np.flatnonzero(keep.ravel())

    def read_model(y):
        x = xr.open_dataset(land.remapped(name, y))[name].values
        return x.reshape(x.shape[0], -1)[:, cells]

    def read_ref(y):
        f = land.REFERENCE[name]
        x = xr.open_dataset(land.land_file(f, y))[f].values
        return v.convert(x.reshape(x.shape[0], -1)[:, cells])

    st = collect(name, cells.size, read_model, read_ref, "land")
    save(name, st, cells, "land")
    lat, lon, ones, lats, lons = grid_010(cells)
    b = bias(name, st)
    report(name, b, lat, lon, ones.astype(bool), "land")
    cold_tail(b, lat, ones.astype(bool))
    draw(name, b, cells, lats, lons, "land")


# --- step --------------------------------------------------------------------


def run_step():
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    lat, lon, lsm, *_ = grid_025(cells)
    regs = {"domaine": np.ones(cells.size, bool)} | {
        k: r for k, r in regions(lat, lon, lsm >= 0.5).items() if k != "sud de 35 N"}
    years = np.array(STEP_YEARS)
    first = MODEL.hist_end + 1
    X = np.stack([np.ones(years.size), years - first, (years >= first).astype(float)], 1)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Saut a {first} ({MODEL.key}, debut du scenario {MODEL.scenario}), "
          f"ajustement droite + marche sur {years[0]}-{years[-1]}, moyennes annuelles ou saisonnieres "
          f"des mailles de la region")
    print("marche +- 2 erreurs types ; ecart type des annees autour de l'ajustement ; marche / ecart type")
    series = {}
    for name in NAMES:
        v = VARS[name]
        scale, u = v.display[0], v.display[2].replace("°C", "K")
        ys = {(r, s): [] for r in regs for s in SEASONS}
        for y in years:
            x, grid = model(name, y)
            x = scale * x[:, cells]
            mo = grid.time.dt.month.values
            for s, ms in SEASONS.items():
                d = x[np.isin(mo, ms)].mean(0)
                for r, sel in regs.items():
                    ys[(r, s)].append(np.nanmean(d[sel]))
        print(f"\n{name} ({u})")
        print("  region | " + " | ".join(SEASONS))
        for r in regs:
            cols = []
            for s in SEASONS:
                y = np.array(ys[(r, s)])
                coef, *_ = np.linalg.lstsq(X, y, rcond=None)
                res = y - X @ coef
                sigma = np.sqrt((res ** 2).sum() / (y.size - 3))
                se = sigma * np.sqrt(np.linalg.inv(X.T @ X)[2, 2])
                cols.append(f"{coef[2]:+.3g} +- {2 * se:.2g} ; {sigma:.2g} ; {coef[2] / sigma:+.1f}")
            print(f"  {r} | " + " | ".join(cols), flush=True)
        series[name] = (np.array(ys[("Europe terre", "annee")]), u)

    fig, axes = plt.subplots(5, 3, figsize=(14, 16), constrained_layout=True)
    for ax, (name, (y, u)) in zip(axes.ravel(), series.items()):
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        ax.plot(years, y, "o-", ms=3, lw=0.8, color="0.3")
        ax.plot(years, X @ coef, color="C3")
        ax.axvline(first - 0.5, color="0.6", ls=":")
        ax.set_title(f"{name} ({u}), marche {coef[2]:+.3g}", fontsize=9)
    fig.suptitle(f"{MODEL.key} brut, Europe terre, moyennes annuelles")
    fig.savefig(OUT / "saut_scenario.png", dpi=110)
    plt.close(fig)


def main(argv: list[str]) -> int:
    if argv[:1] == ["step"]:
        run_step()
        return 0
    if len(argv) == 2 and argv[0] == "bias" and argv[1] in NAMES:
        run_bias(argv[1])
        return 0
    if len(argv) == 2 and argv[0] == "land" and argv[1] in land.REFERENCE:
        run_land(argv[1])
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
