"""Indicateurs annuels de Tn et Tx sur la France métropolitaine, définitions du rapport TRACC de Météo-France (partie 2).

Par maille et par année : jours de très forte chaleur (Tx >= 35 °C), nuits chaudes (Tn > 20 °C), jours de gel
(Tn < 0 °C), Tx de la journée la plus chaude ; puis moyenne sur la France pondérée par la surface.
Grille 0,1° : era5land 1970-2025, cordex010 1970-2100. Écrit figures/climat/france_indicateurs.csv.
"""
import warnings
from pathlib import Path as P

import pandas as pd
import xarray as xr

from france_agregats import BOX, Z, poids  # même contour, mêmes poids

warnings.filterwarnings("ignore")
OUT = P("figures/climat/france_indicateurs.csv")

lignes = []
for groupe in ("era5land", "cordex010"):
    ds = xr.open_zarr(Z, group=groupe, consolidated=False)
    w = poids(ds.tasmax.sel(**BOX))
    ind = {}
    tx = ds.tasmax.sel(**BOX).where(w.notnull()).astype("float32").load()
    ok = tx.notnull().all("time")
    an = tx.groupby("time.year")
    ind["tx35"] = (tx >= 35).groupby("time.year").sum()
    ind["txx"] = an.max()
    del tx, an
    tn = ds.tasmin.sel(**BOX).where(w.notnull()).astype("float32").load()
    ok &= tn.notnull().all("time")
    ind["tn20"] = (tn > 20).groupby("time.year").sum()
    ind["gel"] = (tn < 0).groupby("time.year").sum()
    del tn
    ww = w.where(ok)
    for nom, da in ind.items():
        s = (da * ww).sum(("latitude", "longitude")) / ww.sum()
        for a, v in s.to_series().items():
            lignes.append((groupe, nom, a, v))
    print(groupe, "mailles", int(ww.notnull().sum()), flush=True)

pd.DataFrame(lignes, columns=["source", "indicateur", "annee", "valeur"]).to_csv(OUT, index=False, float_format="%.3f")
print("écrit", OUT)
