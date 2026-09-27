"""Dry spells of ERA5, raw and corrected CORDEX, 1970-2005, by season.

    python -m src.correction.spells

A dry day has less than 1 mm. Spells are cut at the edges of each season
(DJF takes December with the next January and February), the same way for
the three series. For each cell and season: the mean length of the dry
spells, and the longest spell of the season, averaged over the years.

Printed: medians over regions (European land and sea, south of 35 N).
Drawn in data/correction/pr_spells.png (test/ with WSA_QDM_TEST=1): the ERA5 mean length, and the raw and
corrected CORDEX over ERA5 ratios.
"""

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import LogNorm

from src.config import ARCHIVE
from src.correction.check import corrected, raw, run_max
from src.correction.qdm import DAY, TABLES, reference
from src.correction.remap import load_weights

YEARS = range(1970, 2006)
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}
MM = 1 / DAY


def spells(x: np.ndarray, mo: np.ndarray) -> dict:
    """Mean dry-spell length and mean longest spell, per season, (cells,) each."""
    yr = np.concatenate([np.full(366 if y % 4 == 0 else 365, y) for y in YEARS])
    syear = yr + (mo == 12)  # December goes with the next winter
    out = {}
    for s, months in SEASONS.items():
        dry = runs = longest = 0
        blocks = [y for y in YEARS if s != "DJF" or YEARS[0] < y <= YEARS[-1]]
        for y in blocks:
            c = x[(syear == y) & np.isin(mo, months)] < MM
            dry = dry + c.sum(0)
            runs = runs + c[0] + (c[1:] & ~c[:-1]).sum(0)
            longest = longest + run_max(c)
        out[s] = (np.where(runs > 0, dry / np.maximum(runs, 1), 0), longest / len(blocks))
    return out


def main(argv):
    _, keep = load_weights()
    cells = np.flatnonzero(keep.ravel())
    res = {}
    for label, read in (("ERA5", lambda: reference("pr", YEARS, cells)),
                        ("brut", lambda: raw("pr", YEARS, cells)),
                        ("corrige", lambda: corrected("pr", YEARS, cells))):
        x, mo = read()
        res[label] = spells(x, mo)
        del x

    lsm = xr.open_dataarray(ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc")
    lat = np.repeat(lsm.latitude.values, lsm.longitude.size)[cells]
    lon = np.tile(lsm.longitude.values, lsm.latitude.size)[cells]
    land = lsm.values.ravel()[cells] >= 0.5
    europe = (lat >= 35) & (lon >= -10) & (lon <= 40)
    regions = {"Europe terre": europe & land, "Europe mer": europe & ~land, "sud de 35 N": lat < 35}
    for k, title in ((0, "Duree moyenne des series seches (j)"),
                     (1, "Plus longue serie seche de la saison (j)")):
        print(f"\n{title}, mediane sur les mailles : ERA5 | brut | corrige")
        print("saison | " + " | ".join(f"{r:^26s}" for r in regions))
        for s in SEASONS:
            print(f"{s:6s} | " + " | ".join(
                "%6.1f %6.1f %6.1f      " % tuple(np.median(res[d][s][k][r]) for d in res)
                for r in regions.values()))

    def grid(v):
        full = np.full(keep.size, np.nan)
        full[cells] = v
        return full.reshape(keep.shape)

    fig, axes = plt.subplots(4, 3, figsize=(15, 16), constrained_layout=True)
    for i, s in enumerate(SEASONS):
        e = res["ERA5"][s][0]
        im0 = axes[i, 0].pcolormesh(lsm.longitude, lsm.latitude, grid(e), cmap="YlOrBr",
                                    norm=LogNorm(2, 60))
        axes[i, 0].set_title(f"{s} : ERA5, duree moyenne (j)")
        for j, d in ((1, "brut"), (2, "corrige")):
            r = res[d][s][0] / np.where(e > 0, e, np.nan)
            im1 = axes[i, j].pcolormesh(lsm.longitude, lsm.latitude, grid(r), cmap="RdBu_r",
                                        norm=LogNorm(0.4, 2.5))
            axes[i, j].set_title(f"{s} : CORDEX {d} / ERA5")
    fig.colorbar(im0, ax=axes[:, 0], shrink=0.5, label="jours")
    fig.colorbar(im1, ax=axes[:, 1:], shrink=0.5, label="rapport (bleu : trop court)")
    path = TABLES / "pr_spells.png"
    fig.savefig(path, dpi=80)
    print("\ncartes :", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
