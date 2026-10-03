"""Tx moyen de l'été (juin à août) 2091-2100 et écart à 1976-2005, CORDEX corrigé à 0,25°, terres seulement."""
import glob
import warnings
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

warnings.filterwarnings("ignore")
A = "/Volumes/LaCie/weather-simulator-app-V2/data"
BOX = dict(latitude=slice(72, 34), longitude=slice(-12, 40))


def ete(a, b):
    """Moyenne des Tx de juin à août sur les années a à b."""
    somme, n = 0, 0
    for an in range(a, b + 1):
        f = glob.glob(f"{A}/cordex/eur11_025_qdm/tasmax_*_day_{an}0101-{an}1231.nc")[0]
        tx = xr.open_dataset(f).tasmax.sel(**BOX)
        tx = tx.where(tx.time.dt.month.isin([6, 7, 8]), drop=True)
        somme, n = somme + tx.sum("time").load(), n + tx.sizes["time"]
    m = somme / n
    return m - 273.15 if float(m.mean()) > 200 else m


lsm = xr.open_dataset(f"{A}/era5/fixed/lsm_ERA5.nc")
lsm = lsm[list(lsm.data_vars)[0]].squeeze(drop=True).sel(**BOX)
fin = ete(2091, 2100).where(lsm > 0.5)
ref = ete(1976, 2005).where(lsm > 0.5)
d = fin - ref
print(f"écart moyen sur les terres : {float(d.weighted(np.cos(np.deg2rad(d.latitude))).mean()):.2f} K, "
      f"min {float(d.min()):.1f}, max {float(d.max()):.1f}")

fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), sharey=True)
for ax, champ, cmap, vmin, vmax, titre, lab in [
    (axes[0], fin, "YlOrRd", 10, 40, "Tx moyen de l'été, 2091-2100", "°C"),
    (axes[1], d, "RdBu_r", -4, 4, "Écart à 1976-2005", "K"),
]:
    m = ax.pcolormesh(champ.longitude, champ.latitude, champ, cmap=cmap, vmin=vmin, vmax=vmax, shading="auto")
    ax.contour(lsm.longitude, lsm.latitude, lsm, levels=[0.5], colors="#52514e", linewidths=0.4)
    ax.set_title(titre, loc="left", fontsize=12)
    ax.set_aspect(1 / np.cos(np.deg2rad(52)))
    fig.colorbar(m, ax=ax, shrink=0.75, label=lab)
fig.suptitle("Températures maximales de l'été, CORDEX corrigé (EC-EARTH / RCA4, RCP4.5), 0,25°",
             x=0.05, ha="left", fontsize=13)
fig.savefig("figures/cartes/tx_ete_2091-2100.png", dpi=130, bbox_inches="tight")
