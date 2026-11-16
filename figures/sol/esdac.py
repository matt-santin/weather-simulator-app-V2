"""Réserve utile d'ESDAC (European Soil Database Derived data, Hiederer 2013) ramenée sur la grille de 0,25° du site.

    python figures/sol/esdac.py

Entrée : data/sol/esdac/brut (rasters Idrisi de 1 km, ETRS89-LAEA, EPSG:3035), hors dépôt :
la licence interdit de passer les données à des tiers.

Réserve utile = STU_EU_T_TAWC + STU_EU_S_TAWC (version PTF, HYPRES, sur les STU cartographiées) :
eau entre -100 cm (capacité au champ) et -15 000 cm (flétrissement), de 0 à 30 cm pour le sol de
surface et de 30 cm à 100 cm au plus pour le sous-sol, limitée par la profondeur du sol
(Hiederer 2013, p. 41). Une cellule de 1 km à 0 n'a pas de sol décrit (mer, eau, et autres surfaces
sans sol : à vérifier) et n'entre pas dans la moyenne.

Le calcul est celui de src.store.capacity (esdac), qui écrit la réserve servie par le site ;
ce script en garde le détail pour l'analyse. Sortie : data/sol/esdac/reserve_025.nc, par maille de 0,25° : moyenne de la réserve utile (mm),
de ses deux parties, de la profondeur disponible pour les racines (cm), version PTR pour
comparaison, nombre de cellules de 1 km avec sol et part de sol ; et une carte dans figures/sol.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import zarr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.config import DATA  # noqa: E402
from src.store.build import STORE  # noqa: E402

OUT = DATA / "sol" / "esdac" / "reserve_025.nc"
PLACES = {"Grenoble": (45.18, 5.72), "Paris": (48.86, 2.35), "Montpellier": (43.61, 3.88),
          "Séville": (37.39, -5.99), "Pontarlier": (46.90, 6.35), "Beauce": (48.2, 1.6), "Landes": (44.2, -0.8)}


def main():
    from src.store.capacity import esdac, raster

    root = zarr.open_group(STORE, mode="r")
    lat, lon = root["latitude"][:], root["longitude"][:]
    step = abs(lat[1] - lat[0])
    found = esdac(lat, lon, {
        "top": raster("STU_EU_T_TAWC", "<f4"), "sub": raster("STU_EU_S_TAWC", "<f4"),
        "ptr": raster("SMU_EU_T_TAWC", "<f4") + raster("SMU_EU_S_TAWC", "<f4"),
        "depth": raster("STU_EU_DEPTH_ROOTS", "u1").astype("float32")})
    mean = {"total": found["capacity"], **{k: found[k] for k in ("top", "sub", "ptr", "depth")}}
    n, share = found["soil_cells"], found["soil_share"]
    ds = xr.Dataset({
        "capacity": (("latitude", "longitude"), mean["total"].astype("float32"), {"units": "mm", "long_name": "réserve utile, PTF, sol de surface + sous-sol (100 cm au plus)"}),
        "topsoil": (("latitude", "longitude"), mean["top"].astype("float32"), {"units": "mm"}),
        "subsoil": (("latitude", "longitude"), mean["sub"].astype("float32"), {"units": "mm"}),
        "capacity_ptr": (("latitude", "longitude"), mean["ptr"].astype("float32"), {"units": "mm"}),
        "depth_roots": (("latitude", "longitude"), mean["depth"].astype("float32"), {"units": "cm"}),
        "soil_cells": (("latitude", "longitude"), n.astype("float32"), {"long_name": "cellules de 1 km avec sol"}),
        "soil_share": (("latitude", "longitude"), share.astype("float32"), {"long_name": "part des cellules de 1 km avec sol"}),
    }, coords={"latitude": lat, "longitude": lon},
        attrs={"source": "ESDAC, European Soil Database Derived data (Hiederer 2013, doi:10.2788/94128); ne pas redistribuer"})
    ds.to_netcdf(OUT)

    domain = root["domain"][:].astype(bool)
    land = zarr.open_group(DATA / "serve" / "map.zarr", mode="r")["land"][:].astype(bool)
    have = np.isfinite(mean["total"])
    print(f"Mailles terrestres de la carte : {land.sum()}, avec une réserve ESDAC : {(land & have).sum()} "
          f"({100 * (land & have).sum() / land.sum():.1f} %) ; mailles du domaine avec réserve : {(domain & have).sum()}")
    v = mean["total"][land & have]
    print("Réserve utile ESDAC sur les mailles terrestres, centiles 1, 10, 50, 90, 99 :", np.percentile(v, [1, 10, 50, 90, 99]).round(0), "mm")
    print("Part de sol dans la maille, mailles terrestres : centiles 1, 10, 50 :", np.nanpercentile(share[land], [1, 10, 50]).round(2))
    print("\nLieu          réserve PTF  surface  sous-sol   PTR   profondeur racinaire  part de sol")
    for name, (la, lo) in PLACES.items():
        i, j = int(np.abs(lat - la).argmin()), int(np.abs(lon - lo).argmin())
        print(f"{name:12s} {mean['total'][i, j]:8.0f} mm {mean['top'][i, j]:7.0f} {mean['sub'][i, j]:9.0f} {mean['ptr'][i, j]:6.0f} {mean['depth'][i, j]:12.0f} cm {100 * share[i, j]:12.0f} %")
    missing = land & ~have
    if missing.any():
        ii, jj = np.nonzero(missing)
        print(f"\nMailles terrestres sans réserve : {missing.sum()}, latitudes {lat[ii].min():.2f} à {lat[ii].max():.2f}, longitudes {lon[jj].min():.2f} à {lon[jj].max():.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    img = np.where(land, mean["total"], np.nan)
    im = axes[0].imshow(img, extent=(lon[0] - step / 2, lon[-1] + step / 2, lat[-1] - step / 2, lat[0] + step / 2), cmap="YlGnBu", vmin=0, vmax=250)
    axes[0].set_title("Réserve utile ESDAC (PTF, 0-100 cm), mm, à 0,25°"); fig.colorbar(im, ax=axes[0], shrink=0.8)
    im = axes[1].imshow(np.where(land, share, np.nan), extent=(lon[0] - step / 2, lon[-1] + step / 2, lat[-1] - step / 2, lat[0] + step / 2), cmap="Greys_r", vmin=0, vmax=1)
    axes[1].set_title("Part des cellules de 1 km avec sol décrit"); fig.colorbar(im, ax=axes[1], shrink=0.8)
    for ax in axes:
        ax.set_xlim(-25, 45); ax.set_ylim(34, 72); ax.set_aspect(1.5)
    fig.tight_layout(); fig.savefig(Path(__file__).parent / "esdac_reserve.png", dpi=110)


if __name__ == "__main__":
    main()
