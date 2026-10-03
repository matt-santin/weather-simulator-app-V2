"""Température moyenne (tas) sur la France métropolitaine, ERA5-Land et CORDEX corrigé à 0,1°, par période et saison.

Moyenne pondérée par la surface des mailles (cos de la latitude) ; contour Natural Earth 1:50m
(data/fixed/ne_50m_admin_0_countries.geojson, téléchargé s'il manque), Corse comprise.
"""
import json
import urllib.request
import warnings
from pathlib import Path as P

import numpy as np
import xarray as xr
from matplotlib.path import Path

warnings.filterwarnings("ignore")
NE = P("data/fixed/ne_50m_admin_0_countries.geojson")
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"
Z = "data/serve/point.zarr"
PERIODES = [("ERA5-Land", "era5land", 1976, 2005), ("ERA5-Land", "era5land", 1991, 2020),
            ("ERA5-Land", "era5land", 2016, 2025), ("CORDEX", "cordex010", 1976, 2005),
            ("CORDEX", "cordex010", 2016, 2025), ("CORDEX", "cordex010", 2041, 2050),
            ("CORDEX", "cordex010", 2090, 2099), ("CORDEX", "cordex010", 2091, 2100)]

if not NE.exists():
    NE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, NE)
fr = next(f for f in json.load(open(NE))["features"] if f["properties"]["ADMIN"] == "France")
polys = [np.array(p[0]) for p in fr["geometry"]["coordinates"]]
polys = [p for p in polys if -6 < p[:, 0].mean() < 10 and 41 < p[:, 1].mean() < 52]  # métropole

box = dict(latitude=slice(51.5, 41.2), longitude=slice(-5.5, 9.7))
grid = xr.open_zarr(Z, group="era5land", consolidated=False).tas.sel(**box)
lo, la = np.meshgrid(grid.longitude, grid.latitude)
pts = np.c_[lo.ravel(), la.ravel()]
m = np.zeros(len(pts), bool)
for p in polys:
    m |= Path(p).contains_points(pts)
mask = xr.DataArray(m.reshape(lo.shape), coords={"latitude": grid.latitude, "longitude": grid.longitude})
w = np.cos(np.deg2rad(grid.latitude)) * mask

# Le stockage range chaque point sur toute sa série : on lit la France une fois par source.
tas = {g: xr.open_zarr(Z, group=g, consolidated=False).tas.sel(latitude=grid.latitude, longitude=grid.longitude)
       .where(mask).astype("float32").load() for g in ("era5land", "cordex010")}


def moyenne(da, a, b, mois=None):
    s = da.sel(time=slice(str(a), str(b)))
    if mois:
        s = s.where(s.time.dt.month.isin(mois), drop=True)
    clim = s.mean("time")
    ok = clim.notnull() & mask
    return float((clim * w).where(ok).sum() / w.where(ok).sum()), int(ok.sum())


print("source     période    année   été  hiver  mailles")
for nom, g, a, b in PERIODES:
    an, n = moyenne(tas[g], a, b)
    print(f"{nom:10s} {a}-{b} {an:6.2f} {moyenne(tas[g], a, b, [6, 7, 8])[0]:5.2f} "
          f"{moyenne(tas[g], a, b, [12, 1, 2])[0]:5.2f}  {n}")
