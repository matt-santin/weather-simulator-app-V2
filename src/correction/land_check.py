"""Checks of the 0.1 deg correction (src.correction.land), printed.

    python -m src.correction.land_check tasmax
    python -m src.correction.land_check tasmax eobs     parts 3 and 4 only

Run from the repo root, with the external drive plugged in, once land.py has
corrected the variable (and swapped Tn/Tx). Part 1 reads the remapped files:
rebuild them first (land.py remap) if they were deleted. One land cell in STRIDE is used,
about 43 000, as many as the 0.25 deg chain has.

1. Split sample, against ERA5-Land: CAL cut in two halves (1970-1987 and
   1988-2005 for RCA4, 1970-1991 and 1992-2014 for MPI / ICON), calibrated on
   the first, applied to the second (its own years as the model
   distribution, as check.py), and compared with ERA5-Land on the second. Per calendar month: bias of the mean,
   P5 and P95 (mean over cells, and RMS between cells), raw and corrected;
   then W1, the mean gap between quantiles of same rank, median over cells,
   with its floor: ERA5-Land of the first half against the second.
2. Change signal, 2071-2100 against 1976-2005, raw against corrected, mean and
   P95 of winter (DJF) and summer (JJA): QDM should keep it.
3. Against E-OBS 0.1 deg on TEST (after CAL, to 2025), years the correction
   never saw.
   Distributions only, per cell and calendar month (CORDEX does not follow the
   real weather): bias of the mean, P5 and P95, and W1, for CORDEX corrected at
   0.1 deg and at 0.25 deg (the 0.25 cell that holds the 0.1 cell, if
   already corrected), and for
   their references, ERA5-Land and ERA5. By class of E-OBS altitude, January
   and July. Besides the means over a class, which mix biases of both signs,
   the RMS between cells of the bias of the mean: the error on the local
   detail. Then the same over the cells where E-OBS is most reliable, the half
   with the lowest ensemble spread (tx for tasmax, tn for tasmin, both for
   tas). E-OBS centres sit half a cell off the ERA5-Land
   ones: each cell takes the mean of the 4 E-OBS cells around it, all valid
   that day. Cells with E-OBS on fewer than MIN_VALID of the days are left out.
4. A few places, at their own cell (nearest land cell of the full grid):
   January and July means over TEST, from each source.
"""

import sys

import numpy as np
import xarray as xr

from src.config import ARCHIVE
from src.correction.land import OUT, VARS, land_file, load_weights, remapped
from src.correction.land import REFERENCE
from src.correction.models import MODEL
from src.correction.qdm import CAL, calibrate, correct
from src.correction.remap import yearly

STRIDE = 4
EOBS = ARCHIVE / "eobs" / "0.1deg"
EOBS_NAME = {"tasmax": "tx", "tasmin": "tn", "tas": "tg"}
ERA5 = {"tasmax": "mx2t", "tasmin": "mn2t", "tas": "t2m"}
OUT_025 = ARCHIVE / "cordex" / f"{MODEL.out}_025_qdm"
ERA5_DAILY = ARCHIVE / "era5" / "daily"
MIN_VALID = 0.8
ALTITUDES = [(-500, 500), (500, 1000), (1000, 1500), (1500, 5000)]
# Place: latitude, longitude, altitude of the town (m).
PLACES = {"Paris": (48.86, 2.35, 35), "Toulouse": (43.60, 1.44, 146),
          "Marseille": (43.30, 5.37, 40), "Clermont-Ferrand": (45.78, 3.08, 358),
          "Pontarlier": (46.90, 6.35, 837), "Grenoble": (45.19, 5.72, 212),
          "Briancon": (44.90, 6.64, 1326), "Chamonix": (45.92, 6.87, 1035)}
SPREAD = {"tasmax": ("tx",), "tasmin": ("tn",), "tas": ("tx", "tn")}
SPLIT = (CAL[0] + CAL[1] + 1) // 2  # first year of the second half
TEST = range(CAL[1] + 1, 2026)  # E-OBS v33.0e ends 2025-12-31
TEST_LABEL = f"{TEST[0]}-{TEST[-1]}"


def celsius(name):
    return lambda x: x - 273.15


class Grid:
    def __init__(self, places=False):
        _, keep = load_weights()
        self.keep = keep
        g = xr.open_dataset(land_file("t2m", 1970))
        self.lat, self.lon = g.latitude.values, g.longitude.values
        land = np.flatnonzero(keep.ravel())
        self.cells = land[::STRIDE]
        self.n = self.cells.size  # sampled cells; the places follow them
        self.places = {}
        if places:
            li, lj = np.unravel_index(land, keep.shape)
            for name, (la, lo, _) in PLACES.items():
                d = (self.lat[li] - la) ** 2 + ((self.lon[lj] - lo) * np.cos(np.deg2rad(la))) ** 2
                self.places[name] = self.n + len(self.places)
                self.cells = np.append(self.cells, land[np.argmin(d)])
        self.i, self.j = np.unravel_index(self.cells, keep.shape)

    def flat(self, values):
        return values.reshape(values.shape[0], -1)[:, self.cells]


def months(years):
    return np.concatenate([np.arange(f"{y}-01-01", f"{y + 1}-01-01", dtype="datetime64[D]")
                           for y in years]).astype("datetime64[M]").astype(int) % 12 + 1


def read(paths, field, grid, convert=lambda x: x):
    return np.concatenate([convert(grid.flat(xr.open_dataset(p)[field].values)) for p in paths])


def w1(a, b):
    """Mean gap between quantiles of same rank, per cell, (days, cells) each."""
    q = (np.arange(100) + 0.5) / 100
    return np.nanmean(np.abs(np.nanquantile(a, q, axis=0) - np.nanquantile(b, q, axis=0)), axis=0)


def stats(x):
    return np.stack([np.nanmean(x, 0), np.nanpercentile(x, 5, axis=0), np.nanpercentile(x, 95, axis=0)])


# --- 1 ----------------------------------------------------------------------


def split_sample(name, grid):
    v = VARS[name]
    cal, val = range(CAL[0], SPLIT), range(SPLIT, CAL[1] + 1)
    ref = REFERENCE[name]
    ref_c = read([land_file(ref, y) for y in cal], ref, grid, v.convert)
    ref_v = read([land_file(ref, y) for y in val], ref, grid, v.convert)
    raw_c = read([remapped(name, y) for y in cal], name, grid)
    raw_v = read([remapped(name, y) for y in val], name, grid)
    mc, mv = months(cal), months(val)
    yv = np.concatenate([np.full(365 + (y % 4 == 0), y) for y in val])
    to = celsius(name)
    print(f"\n1. Validation croisee contre ERA5-Land : calibration {cal[0]}-{cal[-1]}, "
          f"test {val[0]}-{val[-1]}, "
          f"{grid.cells.size} mailles")
    print("mois | biais moyen brut / corrige | P5 brut / corrige | P95 brut / corrige | "
          "RMS entre mailles (moyenne) brut / corrige | W1 brut / corrige / plancher")
    for m in range(1, 13):
        c = calibrate(ref_c[mc == m], raw_c[mc == m], v)
        x = raw_v[mv == m]
        fixed = np.empty_like(x)
        for y in val:
            now = yv[mv == m] == y
            fixed[now] = correct(x[now], x, c, v)
        r, b, f = stats(ref_v[mv == m]), stats(x), stats(fixed)
        db, df = b - r, f - r
        wr = np.nanmedian(w1(x, ref_v[mv == m]))
        wf = np.nanmedian(w1(fixed, ref_v[mv == m]))
        floor = np.nanmedian(w1(ref_c[mc == m], ref_v[mv == m]))
        print(f"{m:4d} | {np.nanmean(db[0]):+6.2f} / {np.nanmean(df[0]):+6.2f} | "
              f"{np.nanmean(db[1]):+6.2f} / {np.nanmean(df[1]):+6.2f} | "
              f"{np.nanmean(db[2]):+6.2f} / {np.nanmean(df[2]):+6.2f} | "
              f"{np.sqrt(np.nanmean(db[0] ** 2)):5.2f} / {np.sqrt(np.nanmean(df[0] ** 2)):5.2f} | "
              f"{wr:5.2f} / {wf:5.2f} / {floor:5.2f}")
    del ref_c, ref_v, raw_c, raw_v, to


# --- 2 ----------------------------------------------------------------------


def signal(name, grid):
    print("\n2. Signal 2071-2100 moins 1976-2005, moyenne des mailles")
    print("saison | moyenne brut / corrige | P95 brut / corrige | RMS entre mailles de l'ecart corrige - brut (moyenne)")
    for season, ms in (("DJF", (12, 1, 2)), ("JJA", (6, 7, 8))):
        out = {}
        for kind, path in (("brut", remapped), ("corrige", lambda n, y: OUT / yearly(n, y))):
            for label, years in (("passe", range(1976, 2006)), ("futur", range(2071, 2101))):
                xs = []
                for y in years:
                    da = xr.open_dataset(path(name, y))[name]
                    sel = np.isin(da.time.dt.month.values, ms)
                    xs.append(grid.flat(da.values[sel]))
                out[kind, label] = stats(np.concatenate(xs))
        d = {k: out[k, "futur"] - out[k, "passe"] for k in ("brut", "corrige")}
        gap = d["corrige"][0] - d["brut"][0]
        print(f"{season} | {np.nanmean(d['brut'][0]):+5.2f} / {np.nanmean(d['corrige'][0]):+5.2f} | "
              f"{np.nanmean(d['brut'][2]):+5.2f} / {np.nanmean(d['corrige'][2]):+5.2f} | "
              f"{np.sqrt(np.nanmean(gap ** 2)):.2f}")


# --- 3 and 4 ----------------------------------------------------------------


class Eobs:
    """E-OBS 0.1 deg, mean of the 4 cells around each ERA5-Land cell."""

    def __init__(self, name, grid):
        self.field = EOBS_NAME[name]
        self.ds = xr.open_dataset(EOBS / f"{self.field}_ens_mean_0.1deg_reg_v33.0e.nc")
        self.spreads = [xr.open_dataset(EOBS / f"{f}_ens_spread_0.1deg_reg_v33.0e.nc")[f]
                        for f in SPREAD[name]]
        elat, elon = self.ds.latitude.values, self.ds.longitude.values
        lat, lon = grid.lat[grid.i], grid.lon[grid.j]
        # The 4 E-OBS centres around (lat, lon): x.05 off the ERA5-Land x.0, x.1.
        i0 = np.searchsorted(elat, lat) - 1
        j0 = np.searchsorted(elon, lon) - 1
        self.inside = (i0 >= 0) & (i0 + 1 < elat.size) & (j0 >= 0) & (j0 + 1 < elon.size)
        self.i0, self.j0 = np.clip(i0, 0, elat.size - 2), np.clip(j0, 0, elon.size - 2)
        elev = xr.open_dataset(EOBS / "elev_ens_0.1deg_reg_v33.0e.nc").elevation.values
        self.altitude = self.mean4(elev[None])[0]

    def mean4(self, x):
        """(days, lat, lon) to (days, cells): mean of the 4 neighbours, NaN if one is missing."""
        a, b = self.i0, self.j0
        m = (x[:, a, b] + x[:, a + 1, b] + x[:, a, b + 1] + x[:, a + 1, b + 1]) / 4
        m[:, ~self.inside] = np.nan
        return m

    def year(self, y):
        return self.mean4(self.ds[self.field].sel(time=str(y)).values)

    def spread(self, y):
        """Ensemble spread of the year, (days, cells), mean of the fields; None without one."""
        if not self.spreads:
            return None
        return np.mean([self.mean4(s.sel(time=str(y)).values) for s in self.spreads], axis=0)


def against_eobs(name, grid):
    obs = Eobs(name, grid)
    to = celsius(name)
    i25 = np.rint((73.0 - grid.lat[grid.i]) / 0.25).astype(int)
    j25 = np.rint((grid.lon[grid.j] + 45.0) / 0.25).astype(int)
    with_025 = (OUT_025 / yearly(name, TEST[0])).exists()
    series = {k: [] for k in ("E-OBS", "CORDEX 0,1", "CORDEX 0,25", "ERA5-Land", "ERA5")
              if with_025 or k != "CORDEX 0,25"}
    spread = []
    for y in TEST:
        series["E-OBS"].append(obs.year(y))
        spread.append(obs.spread(y))
        series["CORDEX 0,1"].append(to(grid.flat(xr.open_dataset(OUT / yearly(name, y))[name].values)))
        if with_025:
            c25 = xr.open_dataset(OUT_025 / yearly(name, y))[name].values
            series["CORDEX 0,25"].append(to(c25[:, i25, j25]))
        series["ERA5-Land"].append(to(grid.flat(xr.open_dataset(land_file(REFERENCE[name], y))[REFERENCE[name]].values)))
        e = xr.open_dataset(ERA5_DAILY / f"{ERA5[name]}_ERA5_day_{y}0101-{y}1231.nc")[ERA5[name]].values
        series["ERA5"].append(to(e[:, i25, j25]))
    series = {k: np.concatenate(v) for k, v in series.items()}
    spread = None if spread[0] is None else np.concatenate(spread)
    mo = months(TEST)
    ok_obs = np.isfinite(series["E-OBS"])
    ok_obs[:, grid.n:] = False  # the places are read apart, in 4
    print(f"\n3. Contre E-OBS 0,1 deg, {TEST_LABEL}, par classe d'altitude E-OBS "
          f"(mailles avec E-OBS >= {MIN_VALID:.0%} des jours)")
    sources = tuple(k for k in series if k != "E-OBS")
    for m, label in ((1, "janvier"), (7, "juillet")):
        rows = mo == m
        valid = ok_obs[rows].mean(0) >= MIN_VALID
        o_all = np.where(ok_obs[rows], series["E-OBS"][rows], np.nan)
        bias = {k: np.nanmean(np.where(ok_obs[rows], series[k][rows], np.nan), 0) - np.nanmean(o_all, 0)
                for k in sources}
        reliable = None
        if spread is not None:
            sp = np.nanmean(np.where(ok_obs[rows], spread[rows], np.nan), 0)
            reliable = valid & (sp <= np.nanmedian(sp[valid]))
        print(f"\n{label} | classe | mailles | biais moyen / P5 / P95 / W1 / RMS du biais entre mailles, "
              f"pour chaque source")
        for lo, hi in ALTITUDES:
            sel = valid & (obs.altitude >= lo) & (obs.altitude < hi)
            if sel.sum() < 20:
                continue
            o = o_all[:, sel]
            ro = stats(o)
            parts = []
            for k in sources:
                x = np.where(ok_obs[rows][:, sel], series[k][rows][:, sel], np.nan)
                d = stats(x) - ro
                parts.append(f"{k} {np.nanmean(d[0]):+5.2f} {np.nanmean(d[1]):+5.2f} "
                             f"{np.nanmean(d[2]):+5.2f} {np.nanmedian(w1(x, o)):4.2f} "
                             f"{np.sqrt(np.nanmean(bias[k][sel] ** 2)):4.2f}")
            print(f"  {lo:>5}-{hi:<5} m | {sel.sum():6d} | " + " | ".join(parts))
        if reliable is not None:
            print(f"  E-OBS fiable (moitie a faible dispersion), RMS du biais entre mailles :")
            for lo, hi in ALTITUDES:
                sel = reliable & (obs.altitude >= lo) & (obs.altitude < hi)
                if sel.sum() < 20:
                    continue
                parts = [f"{k} {np.sqrt(np.nanmean(bias[k][sel] ** 2)):4.2f}" for k in sources]
                print(f"  {lo:>5}-{hi:<5} m | {sel.sum():6d} | " + " | ".join(parts))

    print(f"\n4. Lieux, a leur maille : moyenne {TEST_LABEL} de {name}, janvier puis juillet")
    for place, k in grid.places.items():
        alt = PLACES[place][2]
        for m in (1, 7):
            vals = " | ".join(f"{s} {np.nanmean(series[s][mo == m, k]):5.1f}" for s in series)
            print(f"  {place:16s} {m:2d} ({grid.lat[grid.i[k]]:.1f} N {grid.lon[grid.j[k]]:.1f} E, "
                  f"ville {alt} m, E-OBS {obs.altitude[k]:4.0f} m) | {vals}")


def main(argv):
    if not 1 <= len(argv) <= 2 or argv[0] not in VARS or argv[1:] not in ([], ["eobs"]):
        print(__doc__)
        return 1
    name = argv[0]
    grid = Grid(places=True)
    if argv[1:] == ["eobs"]:
        against_eobs(name, grid)
        return 0
    print(f"{name} a 0,1 deg contre ERA5-Land ; valeurs en K")
    split_sample(name, grid)
    signal(name, grid)
    against_eobs(name, grid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
