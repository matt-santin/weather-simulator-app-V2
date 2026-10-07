"""Test du candidat CORDEX-CMIP6 contre ERA5-Land et RCA4, 2006-2025.

ICON : CNRM-ESM2-1 / ICON-CLM-202407-1-1 (CLMcom-BTU), EUR-12, historical puis ssp370 (2015).
RCA4 : EC-EARTH r12i1p1 / SMHI-RCA4, EUR-11, rcp45, brut (non corrigé), lu sur le LaCie.
ERA5-Land : groupe era5land de data/serve/point.zarr (0,1°).

Les deux modèles sont lus bruts sur leur grille native : mailles dont le centre est en France
métropolitaine (contour Natural Earth, comme france_agregats.py) et terrestres (sftlf ≥ 50 %),
moyenne simple (mailles quasi égales). ERA5-Land : poids cos(latitude). Villes : maille terrestre
la plus proche dans chaque source (altitudes différentes : l'écart moyen n'a de sens qu'en tendance).

Écrit figures/climat/cmip6_test.csv (indicateurs) et affiche le tableau.
    ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/cmip6_test.py
"""
import glob
import sys
import warnings
from pathlib import Path as P

import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.path import Path

sys.path.insert(0, str(P(__file__).resolve().parent))
from france_agregats import BOX, Z, poids, polys  # noqa: E402

warnings.filterwarnings("ignore")
Y0, Y1 = 2006, 2025
ICON = P("data/cordex/eur12_cnrm-esm2-1_icon-clm")
RCA4 = P("/Volumes/LaCie/weather-simulator-app-V2/data/cordex/eur11")
OUT = P("figures/climat/cmip6_test.csv")
VARS = ["tasmax", "tasmin", "tas"]
VILLES = {"Paris": (48.857, 2.352), "Lyon": (45.760, 4.840), "Bordeaux": (44.838, -0.579),
          "Toulouse": (43.604, 1.444), "Grenoble": (45.179, 5.715), "Madrid": (40.417, -3.704)}


def fichiers(src, var):
    if src == "icon":
        return sorted(glob.glob(str(ICON / f"{var}_EUR-12_*_day_*.nc")))
    return [str(RCA4 / f"{var}_EUR-11_ICHEC-EC-EARTH_{'historical' if y < 2006 else 'rcp45'}"
                       f"_r12i1p1_SMHI-RCA4_v1_day_{y}0101-{y}1231.nc")
            for y in range(Y0, Y1 + 1)]


def sftlf(src):
    f = glob.glob(str(ICON / "sftlf_*.nc"))[0] if src == "icon" else \
        str(RCA4 / "sftlf_EUR-11_ICHEC-EC-EARTH_historical_r0i0p0_SMHI-RCA4_v1_fx.nc")
    return xr.open_dataset(f).sftlf


def masque_france(lat, lon, terre):
    pts = np.c_[lon.ravel(), lat.ravel()]
    m = np.zeros(len(pts), bool)
    for p in polys:
        m |= Path(p).contains_points(pts)
    return m.reshape(lat.shape) & terre


def modele(src, var):
    """Série journalière France et séries des villes (°C), Y0-Y1."""
    ds = xr.open_mfdataset(fichiers(src, var), combine="by_coords")
    ds = ds.sel(time=slice(f"{Y0}", f"{Y1 + 1}-01-01"))
    ds = ds.sel(time=ds.time.dt.year.isin(range(Y0, Y1 + 1)))
    lat, lon = ds.lat.values, ds.lon.values
    terre = sftlf(src).values >= 50
    m = masque_france(lat, lon, terre)
    i, j = np.where(m)
    sub = ds[var].isel(rlat=slice(i.min(), i.max() + 1), rlon=slice(j.min(), j.max() + 1)).load() - 273.15
    msub = m[i.min():i.max() + 1, j.min():j.max() + 1]
    fr = sub.where(xr.DataArray(msub, dims=("rlat", "rlon"))).mean(("rlat", "rlon"))
    villes = {}
    for v, (la, lo) in VILLES.items():
        d = np.where(terre, (lat - la) ** 2 + ((lon - lo) * np.cos(np.deg2rad(la))) ** 2, np.inf)
        a, b = np.unravel_index(np.argmin(d), d.shape)
        villes[v] = (ds[var].isel(rlat=a, rlon=b).load() - 273.15).to_series()
    return fr.to_series(), villes, int(m.sum())


def era5land(var):
    z = xr.open_zarr(Z, group="era5land", consolidated=False)[var].sel(time=slice(f"{Y0}", f"{Y1}"))
    da = z.sel(**BOX)
    w = poids(da)
    da = da.where(w.notnull()).astype("float32").load()
    w = w.where(da.notnull().all("time"))
    fr = ((da * w).sum(("latitude", "longitude")) / w.sum()).to_series()
    villes = {}
    for v, (la, lo) in VILLES.items():
        box = z.sel(latitude=slice(la + 0.2, la - 0.2), longitude=slice(lo - 0.2, lo + 0.2)).load()
        ok = box.notnull().all("time")
        d = ((box.latitude - la) ** 2 + ((box.longitude - lo) * np.cos(np.deg2rad(la))) ** 2).where(ok)
        a, b = np.unravel_index(int(d.fillna(np.inf).argmin()), d.shape)
        villes[v] = box.isel(latitude=a, longitude=b).to_series().astype("float32")
    off = 273.15 if fr.mean() > 100 else 0.0
    return fr - off, {k: s - off for k, s in villes.items()}, int(w.notnull().sum())


def indicateurs(s):
    """Été (JJA) : moyenne, P90, P99, tendance des moyennes estivales (K/décennie) ; tendance annuelle."""
    s.index = pd.to_datetime(s.index).normalize()
    ete = s[s.index.month.isin([6, 7, 8])]
    jja = ete.groupby(ete.index.year).mean()
    an = s.groupby(s.index.year).mean()
    pente = lambda x: 10 * np.polyfit(x.index.values, x.values, 1)[0]
    return {"moy_JJA": ete.mean(), "P90_JJA": ete.quantile(0.9), "P99_JJA": ete.quantile(0.99),
            "tend_JJA": pente(jja), "tend_AN": pente(an)}


if __name__ == "__main__":
    lignes = []
    for var in VARS:
        for src, f in [("era5land", era5land), ("icon", lambda v: modele("icon", v)),
                       ("rca4", lambda v: modele("rca4", v))]:
            fr, villes, n = f(var)
            print(f"{var} {src}: {n} mailles France, {len(fr)} jours", flush=True)
            lignes.append({"variable": var, "source": src, "lieu": "France", **indicateurs(fr)})
            for v, s in villes.items():
                lignes.append({"variable": var, "source": src, "lieu": v, **indicateurs(s)})
    df = pd.DataFrame(lignes)
    df.to_csv(OUT, index=False, float_format="%.3f")
    pd.set_option("display.width", 200)
    for var in VARS:
        t = df[df.variable == var].pivot(index="lieu", columns="source")
        print(f"\n== {var}")
        print(t.round(2).to_string())
    print("écrit", OUT)
