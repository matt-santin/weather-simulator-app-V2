"""Paris-Montsouris face à E-OBS, ERA5-Land et à la simulation corrigée, 1970-2019, maille 0,1°.

    python figures/climat/montsouris.py
    python figures/climat/montsouris.py eobs     simulation corrigée contre E-OBS,
                                                 lue sur le disque externe (cordex/<modèle>_010_qdm_eobs)

Relevés de data/stations/paris_montsouris.csv (1900-2019). E-OBS v33.0e à
0,1° (disque externe, environ 45 s par grandeur), ERA5-Land et la simulation
corrigée (groupe cordex010 du stockage, modèle lu dans son attribut
simulation) à la maille de 0,1° la plus proche de la station. E-OBS est
interpolé à partir de stations : Montsouris est probablement dans son réseau,
il n'en est donc pas indépendant.

E-OBS et ERA5-Land suivent le temps qu'il a fait : ils se comparent à la
station jour par jour.
La simulation ne suit pas les dates : elle ne se compare que par ses
statistiques (moyennes, quantiles, tendance, maximum annuel).

Sorties : figures/climat/montsouris_<modèle>.png, chiffres dans
figures/climat/montsouris_<modèle>.log.
"""
import sys
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from src.config import ARCHIVE

warnings.filterwarnings("ignore")
Z = "data/serve/point.zarr"
STATION = "data/stations/paris_montsouris.csv"
LAT, LON = 48.82, 2.34  # Paris-Montsouris
P0, P1 = 1970, 2019  # période commune
TAG = {"RCA4": "RCA4", "ICON-CLM": "MPI"}
NAMES = {"t_max": "tasmax", "t_min": "tasmin"}
EOBS = ARCHIVE / "eobs" / "0.1deg"
BLUE, ORANGE, GREY, GREEN = "#2a78d6", "#eb6834", "#52514e", "#2f9e5b"

obs = pd.read_csv(STATION, index_col=0, parse_dates=True)[["t_min", "t_max"]]
obs.loc[obs.t_min > obs.t_max] = np.nan  # une erreur de saisie : le jour est écarté

sim = xr.open_zarr(Z, group="cordex010", consolidated=False).tasmax.attrs["simulation"]
tag = TAG[sim["regional"]]
model = f"{sim['driving']} / {sim['regional']}"
FROM_EOBS = sys.argv[1:] == ["eobs"]
REF = "E-OBS" if FROM_EOBS else "ERA5-Land"
if FROM_EOBS:
    tag += "_eobs"


def series(group: str) -> tuple[pd.DataFrame, tuple[float, float]]:
    ds = xr.open_zarr(Z, group=group, consolidated=False)
    cell = ds.sel(latitude=LAT, longitude=LON, method="nearest")
    out = pd.DataFrame({k: cell[v].sel(time=slice(f"{P0}", f"{P1}")).to_series() for k, v in NAMES.items()})
    return out, (float(cell.latitude), float(cell.longitude))


def eobs() -> tuple[pd.DataFrame, tuple[float, float]]:
    out, at = {}, None
    for k, e in (("t_max", "tx"), ("t_min", "tn")):
        da = xr.open_dataset(EOBS / f"{e}_ens_mean_0.1deg_reg_v33.0e.nc")[e]
        cell = da.sel(latitude=LAT, longitude=LON, method="nearest").sel(time=slice(f"{P0}", f"{P1}"))
        out[k] = cell.load().to_series()
        at = (float(cell.latitude), float(cell.longitude))
    return pd.DataFrame(out), at


def corrected_eobs() -> pd.DataFrame:
    """Simulation corrigée contre E-OBS, fichiers annuels (pas encore dans le stockage)."""
    from src.correction.models import MODELS
    out = ARCHIVE / "cordex" / f"{MODELS[tag[:-5].lower()].out}_010_qdm_eobs"
    cols = {}
    for k, v in NAMES.items():
        parts = []
        for y in range(P0, P1 + 1):
            da = xr.open_dataset(next(out.glob(f"{v}_*_day_{y}0101-{y}1231.nc")))[v]
            parts.append(da.sel(latitude=LAT, longitude=LON, method="nearest").to_series() - 273.15)
        cols[k] = pd.concat(parts)
    return pd.DataFrame(cols)


land, where = series("era5land")
mod = corrected_eobs() if FROM_EOBS else series("cordex010")[0]
eo, where_eo = eobs()
st = obs.loc[f"{P0}":f"{P1}"]
lines = [f"Paris-Montsouris ({LAT} N, {LON} E), {P0}-{P1} ; maille 0,1° ERA5-Land et simulation "
         f"{where[0]:.2f} N {where[1]:.2f} E, E-OBS {where_eo[0]:.2f} N {where_eo[1]:.2f} E",
         f"Simulation : {model}, {sim['scenario']}, corrigée contre {REF} sur "
         f"{sim['calibration_start'][:4]}-{sim['calibration_end'][:4]}", ""]

# 1. Écart moyen par mois.
FRAMES = {"station": st, "eobs": eo, "land": land, "mod": mod}
LABELS = {"station": "station", "eobs": "E-OBS", "land": "ERA5-Land", "mod": "simulation"}
SOURCES = ("eobs", "land", "mod")
month = {name: df.groupby(df.index.month).mean() for name, df in FRAMES.items()}
lines.append("Écart moyen par mois (°C), source - station")
lines.append("mois  " + "  ".join(f"Tx {LABELS[n]:>10s}" for n in SOURCES) + "  "
             + "  ".join(f"Tn {LABELS[n]:>10s}" for n in SOURCES))
for m in range(1, 13):
    lines.append(f"{m:4d}  " + "  ".join(f"{month[n].t_max[m] - month['station'].t_max[m]:+13.2f}" for n in SOURCES)
                 + "  " + "  ".join(f"{month[n].t_min[m] - month['station'].t_min[m]:+13.2f}" for n in SOURCES))
for k, label in (("t_max", "Tx"), ("t_min", "Tn")):
    lines.append(f"Année {label} : " + ", ".join(
        f"{LABELS[n]} {FRAMES[n][k].mean() - st[k].mean():+.2f}" for n in SOURCES))
lines.append("")

# 2. E-OBS et ERA5-Land jour par jour.
for n in ("eobs", "land"):
    for k, label in (("t_max", "Tx"), ("t_min", "Tn")):
        both = pd.concat({"st": st[k], "src": FRAMES[n][k]}, axis=1).dropna()
        d = both.src - both.st
        lines.append(f"{LABELS[n]} jour par jour, {label} : corrélation {both.corr().iloc[0, 1]:.3f}, "
                     f"écart quadratique {np.sqrt((d ** 2).mean()):.2f} °C, "
                     f"écart absolu > 3 °C {100 * (d.abs() > 3).mean():.1f} % des jours")
lines.append("")

# 3. Quantiles de Tx d'été.
summer = lambda df: df.t_max[df.index.month.isin([6, 7, 8])].dropna()
q = np.arange(1, 100)
qs = {name: np.percentile(summer(df), q) for name, df in FRAMES.items()}
lines.append("Tx d'été (juin-août), quantiles (°C) : station / E-OBS / ERA5-Land / simulation")
for p in (5, 25, 50, 75, 95, 99):
    lines.append(f"  {p:2d} % : " + " / ".join(f"{qs[n][p - 1]:5.1f}" for n in FRAMES))
hot = lambda df: summer(df)[summer(df) >= np.percentile(summer(df), 95)].mean()
for n in SOURCES:
    lines.append(f"Moyenne des 5 % de journées d'été les plus chaudes, {LABELS[n]} - station : "
                 f"{hot(FRAMES[n]) - hot(st):+.2f} °C")
lines.append("")

# 4. Tendance du Tx d'été.
jja = {name: df.t_max[df.index.month.isin([6, 7, 8])].groupby(df.index.year[df.index.month.isin([6, 7, 8])]).mean()
       for name, df in (FRAMES | {"station": obs}).items()}
lines.append(f"Tendance du Tx moyen d'été {P0}-{P1} (°C par décennie, moindres carrés)")
trend = {}
for name, label in LABELS.items():
    s = jja[name].loc[P0:P1]
    trend[name] = np.polyfit(s.index, s.values, 1)
    lines.append(f"  {label:10s} {10 * trend[name][0]:+.2f}")
s = jja["station"].loc[1900:1969]
lines.append(f"  station 1900-1969 : {10 * np.polyfit(s.index, s.values, 1)[0]:+.2f}")
lines.append("")

# 5. Tx maximal de l'année.
txx = {name: df.t_max.groupby(df.index.year).max().loc[P0:P1] for name, df in (FRAMES | {"station": obs}).items()}
lines.append("Tx maximal de l'année, moyenne (°C) : " + ", ".join(f"{LABELS[n]} {txx[n].mean():.1f}" for n in LABELS))
for n in ("eobs", "land"):
    gap = txx[n] - txx["station"]
    lines.append(f"{LABELS[n]} - station, même année : moyenne {gap.mean():+.2f}, de {gap.min():+.1f} à {gap.max():+.1f} °C")
for y in (2003, 2019):
    lines.append(f"  {y} : " + ", ".join(f"{LABELS[n]} {txx[n][y]:.1f}" for n in ("station", "eobs", "land")))

text = "\n".join(lines)
print(text)
open(f"figures/climat/montsouris_{tag}.log", "w").write(text + "\n")

# Figure.
fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
a = axes[0, 0]
months = np.arange(1, 13)
for name, colour, label in (("eobs", GREEN, "E-OBS"), ("land", BLUE, "ERA5-Land"),
                            ("mod", ORANGE, f"simulation ({model})")):
    a.plot(months, month[name].t_max - month["station"].t_max, color=colour, lw=2, label=f"Tx, {label}")
    a.plot(months, month[name].t_min - month["station"].t_min, color=colour, lw=1.2, ls="--", label=f"Tn, {label}")
a.axhline(0, color=GREY, lw=0.8)
a.set_xticks(months, ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
a.set_ylabel("source - station (°C)")
a.set_title(f"Écart moyen par mois, {P0}-{P1}", loc="left", fontsize=11)
a.legend(frameon=False, fontsize=8)

a = axes[0, 1]
for name, colour, label in (("eobs", GREEN, "E-OBS"), ("land", BLUE, "ERA5-Land"), ("mod", ORANGE, "simulation")):
    a.plot(q, qs[name] - qs["station"], color=colour, lw=2, label=label)
a.axhline(0, color=GREY, lw=0.8)
a.set_xlabel("quantile (%)")
a.set_ylabel("source - station (°C)")
a.set_title(f"Tx d'été (juin-août), écart par quantile, {P0}-{P1}", loc="left", fontsize=11)
a.legend(frameon=False, fontsize=8)

a = axes[1, 0]
a.plot(jja["station"].index, jja["station"], color=GREY, lw=1, alpha=0.6, label="station")
for name, colour, label in (("eobs", GREEN, "E-OBS"), ("land", BLUE, "ERA5-Land"), ("mod", ORANGE, "simulation")):
    a.plot(jja[name].index, jja[name], color=colour, lw=1, alpha=0.6, label=label)
for name, colour in (("station", GREY), ("eobs", GREEN), ("land", BLUE), ("mod", ORANGE)):
    x = np.arange(P0, P1 + 1)
    a.plot(x, np.polyval(trend[name], x), color=colour, lw=2.2)
a.set_ylabel("Tx moyen d'été (°C)")
a.set_title(f"Tx moyen d'été, tendances {P0}-{P1} (traits épais)", loc="left", fontsize=11)
a.legend(frameon=False, fontsize=8, loc="upper left")

a = axes[1, 1]
for name, colour, label in (("station", GREY, "station"), ("eobs", GREEN, "E-OBS"), ("land", BLUE, "ERA5-Land"),
                            ("mod", ORANGE, "simulation")):
    a.plot(txx[name].index, txx[name], color=colour, lw=1.4, label=label)
a.set_ylabel("Tx maximal de l'année (°C)")
a.set_title("Tx maximal de l'année", loc="left", fontsize=11)
a.legend(frameon=False, fontsize=8, loc="upper left")

for a in axes.flat:
    a.grid(axis="y", color="#e5e4e0", lw=0.8)
    a.spines[["top", "right"]].set_visible(False)
fig.suptitle(f"Paris-Montsouris face à E-OBS, ERA5-Land et à la simulation corrigée contre {REF} ({model}, {sim['scenario']}), maille 0,1°",
             x=0.02, ha="left", fontsize=12)
fig.tight_layout()
fig.savefig(f"figures/climat/montsouris_{tag}.png", dpi=150)
