"""Tx et géopotentiel à 500 hPa, CORDEX corrigé à 0,25°, autour de la canicule parisienne du 10/08/2083."""
import warnings
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

warnings.filterwarnings("ignore")
A = "/Volumes/LaCie/weather-simulator-app-V2/data"
F = "_EUR-11_ICHEC-EC-EARTH_rcp45_r12i1p1_SMHI-RCA4_v1_day_20830101-20831231.nc"
BOX = dict(latitude=slice(62, 35), longitude=slice(-15, 25))
JOURS = ["2083-08-07", "2083-08-08", "2083-08-09", "2083-08-10", "2083-08-11", "2083-08-12"]
VILLES = {"Paris": (48.86, 2.35), "Lyon": (45.76, 4.84)}

tx = xr.open_dataset(f"{A}/cordex/eur11_025_qdm/tasmax{F}").tasmax.sel(time=JOURS, **BOX)
zg = xr.open_dataset(f"{A}/cordex/eur11_025_qdm/zg500{F}").zg500.sel(time=JOURS, **BOX)
if float(tx.mean()) > 200:
    tx = tx - 273.15
lsm = xr.open_dataset(f"{A}/era5/fixed/lsm_ERA5.nc")
lsm = lsm[list(lsm.data_vars)[0]].squeeze(drop=True).sel(**BOX)

fig, axes = plt.subplots(2, 3, figsize=(14, 8.5), sharex=True, sharey=True)
for ax, j in zip(axes.flat, JOURS):
    m = ax.pcolormesh(tx.longitude, tx.latitude, tx.sel(time=j), cmap="YlOrRd", vmin=15, vmax=44, shading="auto")
    ax.contour(lsm.longitude, lsm.latitude, lsm, levels=[0.5], colors="#52514e", linewidths=0.5)
    cs = ax.contour(zg.longitude, zg.latitude, zg.sel(time=j), levels=np.arange(5500, 6100, 40), colors="#0b0b0b", linewidths=0.8)
    ax.clabel(cs, fmt="%d", fontsize=7)
    for v, (la, lo) in VILLES.items():
        ax.plot(lo, la, "o", ms=4, mfc="white", mec="#0b0b0b")
        ax.annotate(f"{v} {float(tx.sel(time=j, latitude=la, longitude=lo, method='nearest')):.0f}",
                    (lo, la), xytext=(4, 3), textcoords="offset points", fontsize=8)
    ax.set_title(j, loc="left", fontsize=11)
    ax.set_aspect(1 / np.cos(np.deg2rad(48)))
fig.colorbar(m, ax=axes, shrink=0.8, label="Tx (°C)")
fig.suptitle("Canicule d'août 2083 : Tx (couleurs) et géopotentiel à 500 hPa (traits, m), CORDEX corrigé 0,25°",
             x=0.05, ha="left", fontsize=13)
fig.savefig("figures/cartes/canicule_2083.png", dpi=130, bbox_inches="tight")
