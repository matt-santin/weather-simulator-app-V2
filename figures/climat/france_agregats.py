"""Agrégats annuels et saisonniers sur la France métropolitaine (Corse comprise).

tas, tasmax, tasmin : grille 0,1° (era5land 1970-2025, cordex010 1970-2100), moyennes annuelles et saisonnières.
pr : grille 0,25° (era5 1970-2025, cordex 1970-2100), cumuls saisonniers (mm), hiver = décembre de l'année
précédente à février. Moyennes pondérées par la surface des mailles ; contour Natural Earth 1:50m.
Écrit figures/climat/france_agregats.csv (une ligne par source, variable, année, saison).
"""
import json
import urllib.request
import warnings
from pathlib import Path as P

import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.path import Path

warnings.filterwarnings("ignore")
NE = P("data/fixed/ne_50m_admin_0_countries.geojson")
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"
Z = "data/serve/point.zarr"
OUT = P("figures/climat/france_agregats.csv")
BOX = dict(latitude=slice(51.6, 41.2), longitude=slice(-5.6, 9.8))
SAISONS = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM",
           6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}

if not NE.exists():
    NE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, NE)
fr = next(f for f in json.load(open(NE))["features"] if f["properties"]["ADMIN"] == "France")
polys = [np.array(p[0]) for p in fr["geometry"]["coordinates"]]
polys = [p for p in polys if -6 < p[:, 0].mean() < 10 and 41 < p[:, 1].mean() < 52]  # métropole


def poids(da):
    """Poids de surface des mailles dont le centre est en France, sur la grille de da."""
    lo, la = np.meshgrid(da.longitude, da.latitude)
    pts = np.c_[lo.ravel(), la.ravel()]
    m = np.zeros(len(pts), bool)
    for p in polys:
        m |= Path(p).contains_points(pts)
    m = xr.DataArray(m.reshape(lo.shape), coords={"latitude": da.latitude, "longitude": da.longitude})
    return (np.cos(np.deg2rad(da.latitude)) * m).where(m)


def serie(groupe, var):
    """Moyenne spatiale journalière sur la France (mailles valides tous les jours seulement)."""
    da = xr.open_zarr(Z, group=groupe, consolidated=False)[var].sel(**BOX)
    w = poids(da)
    da = da.where(w.notnull()).astype("float32").load()
    w = w.where(da.notnull().all("time"))
    s = (da * w).sum(("latitude", "longitude")) / w.sum()
    return s.to_series(), int(w.notnull().sum())


if __name__ == "__main__":
    lignes = []
    for groupe, var in [("era5land", "tas"), ("era5land", "tasmax"), ("era5land", "tasmin"),
                        ("cordex010", "tas"), ("cordex010", "tasmax"), ("cordex010", "tasmin"),
                        ("era5", "pr"), ("cordex", "pr")]:
        s, n = serie(groupe, var)
        an = s.index.year + (s.index.month == 12)  # décembre compté dans l'hiver suivant
        sai = s.index.month.map(SAISONS)
        agg = "sum" if var == "pr" else "mean"
        d = s.groupby([an, sai]).agg([agg, "size"])
        for (a, sa), (v, k) in d.iterrows():
            lignes.append((groupe, var, a, sa, v, k))
        ann = s.groupby(s.index.year).agg([agg, "size"])
        for a, (v, k) in ann.iterrows():
            lignes.append((groupe, var, a, "AN", v, k))
        print(groupe, var, "mailles", n, flush=True)

    df = pd.DataFrame(lignes, columns=["source", "variable", "annee", "saison", "valeur", "jours"])
    df.to_csv(OUT, index=False, float_format="%.3f")
    print("écrit", OUT, len(df))
