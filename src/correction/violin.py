"""Distribution of ERA5, raw and corrected CORDEX at one cell and month, 1970-2005.

    python -m src.correction.violin tas 48.86 2.35 1 Paris

Left: both distributions as violins, the quantiles of same rank joined, which
is what the QDM matches. Right: the bias table b(tau) = Q_ERA5 - Q_CORDEX of
that cell, the correction a day of rank tau receives. CORDEX is the field
remapped to the ERA5 0.25 deg grid, before and after QDM. The corrected years
used their own sliding window, not 1970-2005, so they need not match ERA5
exactly.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from src.config import ARCHIVE
from src.correction.qdm import CAL, ERA5_NAME, LEVELS, OUT, quantiles
from src.correction.remap import target as remapped

FIG = Path(__file__).resolve().parents[2] / "figures" / "correction"
ERA5_COLOR, CORDEX_COLOR, FIXED_COLOR = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED = "#1f1f1e", "#8a8983"
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre"]
MARKS = (0.05, 0.25, 0.5, 0.75, 0.95)


def series(path, name, lat, lon, month):
    da = xr.open_dataset(path)[name].sel(latitude=lat, longitude=lon, method="nearest")
    return da.where(da.time.dt.month == month, drop=True), da.latitude.item(), da.longitude.item()


def main(argv):
    if len(argv) != 5:
        print(__doc__)
        return 1
    name, lat, lon, month, place = argv[0], float(argv[1]), float(argv[2]), int(argv[3]), argv[4]
    years = range(CAL[0], CAL[1] + 1)
    v = ERA5_NAME[name]
    era, cor, fix = [], [], []
    for y in years:
        e, glat, glon = series(ARCHIVE / "era5" / "daily" / f"{v}_ERA5_day_{y}0101-{y}1231.nc",
                               v, lat, lon, month)
        era.append(e.values)
        cor.append(series(remapped(name, y), name, lat, lon, month)[0].values)
        fix.append(series(OUT / remapped(name, y).name, name, lat, lon, month)[0].values)
    era = np.concatenate(era) - 273.15
    cor = np.concatenate(cor) - 273.15
    fix = np.concatenate(fix) - 273.15
    qe, qc = quantiles(era[:, None])[:, 0], quantiles(cor[:, None])[:, 0]

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED})
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw={"width_ratios": [1.5, 1]},
                               constrained_layout=True)

    parts = a.violinplot([era, cor, fix], positions=[0, 1, 2], widths=0.8, showextrema=False)
    for body, color in zip(parts["bodies"], (ERA5_COLOR, CORDEX_COLOR, FIXED_COLOR)):
        body.set_facecolor(color)
        body.set_edgecolor(color)
        body.set_alpha(0.35)
    labels = []
    for p in MARKS:
        ye, yc, yf = np.quantile(era, p), np.quantile(cor, p), np.quantile(fix, p)
        a.plot([0, 1, 2], [ye, yc, yf], color=MUTED, lw=1, ls=":", zorder=1)
        for x, y, color in ((0, ye, ERA5_COLOR), (1, yc, CORDEX_COLOR), (2, yf, FIXED_COLOR)):
            a.plot([x - 0.12, x + 0.12], [y, y], color=color, lw=2)
        labels.append((yf, f"P{round(100 * p)} : b = {round(ye - yc, 1) + 0:+.1f} K, "
                           f"corrigé - ERA5 = {round(yf - ye, 1) + 0:+.1f} K"))
    # Labels sit at their corrected quantile, pushed apart when too close.
    lo, hi = a.get_ylim()
    gap, prev = 0.05 * (hi - lo), -np.inf
    for y, text in sorted(labels):
        prev = max(y, prev + gap)
        a.text(2.5, prev, text, va="center", color=INK, fontsize=9)
    a.set_xticks([0, 1, 2], [f"ERA5\n({len(era)} jours)", f"CORDEX brut\n({len(cor)} jours)",
                             f"CORDEX corrigé\n({len(fix)} jours)"])
    a.set_xlim(-0.5, 4.3)
    a.set_ylabel(f"{name} journalière (°C)")
    a.grid(axis="y", color="#e6e5df", lw=0.8)
    a.set_axisbelow(True)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    a.set_title(f"Distributions, quantiles de même rang reliés", color=INK, loc="left")

    b.axhline(0, color=MUTED, lw=0.8)
    b.plot(100 * LEVELS, qe - qc, color=INK, lw=2)
    for p in MARKS:
        k = np.abs(LEVELS - p).argmin()
        b.plot(100 * LEVELS[k], qe[k] - qc[k], "o", ms=8, color=INK, mec=INK)
    b.set_xlabel("rang du jour dans sa distribution CORDEX, tau (%)")
    b.set_ylabel("correction b(tau) = Q_ERA5 - Q_CORDEX (K)")
    b.grid(color="#e6e5df", lw=0.8)
    b.set_axisbelow(True)
    for s in ("top", "right"):
        b.spines[s].set_visible(False)
    b.set_title("Correction ajoutée à un jour selon son rang", color=INK, loc="left")

    ns, ew = ("N" if glat >= 0 else "S"), ("E" if glon >= 0 else "W")
    fig.suptitle(f"{place} (maille ERA5 {abs(glat):.2f} {ns}, {abs(glon):.2f} {ew}), {MONTHS[month - 1]} "
                 f"{CAL[0]}-{CAL[1]}", color=INK, x=0.01, ha="left", fontsize=12)
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / f"{name}_{place.lower()}_{month:02d}_violin.png"
    fig.savefig(path, dpi=120)
    print(path)
    print("moyenne ERA5 %.2f, CORDEX brut %.2f, CORDEX corrige %.2f" % (era.mean(), cor.mean(), fix.mean()))
    print("min ERA5 %.2f, brut %.2f, corrige %.2f" % (era.min(), cor.min(), fix.min()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
