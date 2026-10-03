"""Grandeurs de la page « Météo-France éclaire le climat en France jusqu'en 2100 », calculées sur nos données.

Séries journalières sur la France (Tmoy = (Tn + Tx)/2, moyenne de surface), Tx maximal de toutes les mailles,
écarts régionaux de tas (nord-ouest, sud-est et Alpes), pluie annuelle du quart nord-est, maximum annuel de
la pluie journalière (RX1day) moyenné sur les mailles. Écrit figures/climat/france_meteofrance_*.csv.
"""
import warnings

import numpy as np
import pandas as pd
import xarray as xr

from france_agregats import BOX, Z, poids

warnings.filterwarnings("ignore")
REGIONS = {  # boîtes en degrés, appliquées aux mailles françaises
    "nord-ouest": dict(lon=(-5.6, 0.5), lat=(46.5, 51.6)),
    "sud-est et Alpes": dict(lon=(4.5, 7.8), lat=(43.0, 46.5)),
    "quart nord-est": dict(lon=(2.5, 8.3), lat=(46.5, 51.6)),
}


def charge(groupe, var):
    da = xr.open_zarr(Z, group=groupe, consolidated=False)[var].sel(**BOX)
    w = poids(da)
    return da.where(w.notnull()).astype("float32").load(), w


def moy(da, w):
    w = w.where(da.notnull().all("time"))
    return (da * w).sum(("latitude", "longitude")) / w.sum()


def region(w, r):
    b = REGIONS[r]
    lo, la = w.longitude, w.latitude
    return w.where((lo >= b["lon"][0]) & (lo < b["lon"][1]) & (la >= b["lat"][0]) & (la < b["lat"][1]))


jour, annee = {}, []
for groupe in ("era5land", "cordex010"):
    tx, w = charge(groupe, "tasmax")
    jour[(groupe, "tx")] = moy(tx, w).to_series()
    jour[(groupe, "txmax")] = tx.max(("latitude", "longitude")).to_series()
    del tx
    tn, w = charge(groupe, "tasmin")
    jour[(groupe, "tn")] = moy(tn, w).to_series()
    del tn
    tas, w = charge(groupe, "tas")
    an = tas.groupby("time.year").mean()
    for r in ("nord-ouest", "sud-est et Alpes"):
        s = moy(an.rename(year="time"), region(w, r)).to_series()
        annee += [(groupe, "tas " + r, a, v) for a, v in s.items()]
    del tas, an
    print(groupe, "températures", flush=True)

for groupe in ("era5", "cordex"):
    pr, w = charge(groupe, "pr")
    an = pr.groupby("time.year")
    s = moy(an.sum().rename(year="time"), region(w, "quart nord-est")).to_series()
    annee += [(groupe, "pr quart nord-est", a, v) for a, v in s.items()]
    s = moy(an.max().rename(year="time"), w).to_series()
    annee += [(groupe, "rx1day", a, v) for a, v in s.items()]
    del pr, an
    print(groupe, "précipitations", flush=True)

pd.DataFrame(jour).to_csv("figures/climat/france_meteofrance_jour.csv", float_format="%.3f")
pd.DataFrame(annee, columns=["source", "grandeur", "annee", "valeur"]).to_csv(
    "figures/climat/france_meteofrance_annee.csv", index=False, float_format="%.3f")
print("écrit")
