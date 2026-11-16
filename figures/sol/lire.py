"""Rayonnements et évaporation aux lieux d'essai, lus sur le disque externe.

    python figures/sol/lire.py

ERA5 1970-2025 (ssrd, ssr, strd, e) et MPI / ICON corrigé 1970-2100 (rsds, rsus,
rlds, evspsbl), à la maille 0,25° de chaque lieu. Sortie : data/sol/points.npz,
en W m-2 pour les rayonnements et en mm/jour pour l'évaporation (positive vers
le haut), un tableau jours x lieux par champ.
"""
import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import ARCHIVE, DATA  # noqa: E402
from src.correction.models import MODEL  # noqa: E402

PLACES = {"Grenoble": (45.18, 5.72), "Paris": (48.86, 2.35), "Montpellier": (43.61, 3.88),
          "Séville": (37.39, -5.99), "Pontarlier": (46.90, 6.35)}
DAY = 86400.0
ERA5 = {"ssrd": 1 / DAY, "ssr": 1 / DAY, "strd": 1 / DAY, "e": -1000.0}
CORDEX = {"rsds": 1.0, "rsus": 1.0, "rlds": 1.0, "evspsbl": DAY}


def read(path, lat, lon):
    with xr.open_dataset(path) as ds:
        da = ds[next(iter(ds.data_vars))]
        return da.sel(latitude=lat, longitude=lon, method="nearest").values.astype("float32")


def main():
    lat = xr.DataArray([p[0] for p in PLACES.values()], dims="p")
    lon = xr.DataArray([p[1] for p in PLACES.values()], dims="p")
    out = {"places": np.array(list(PLACES)), "lat": lat.values, "lon": lon.values,
           "era5_start": np.datetime64("1970-01-01"), "cordex_start": np.datetime64("1970-01-01")}
    for name, k in ERA5.items():
        parts = [read(ARCHIVE / "era5" / "daily" / f"{name}_ERA5_day_{y}0101-{y}1231.nc", lat, lon)
                 for y in range(1970, 2026)]
        out[f"era5_{name}"] = np.concatenate(parts) * k
        print("era5", name, out[f"era5_{name}"].shape, flush=True)
    folder = ARCHIVE / "cordex" / f"{MODEL.out}_025_qdm"
    for name, k in CORDEX.items():
        parts = [read(folder / MODEL.yearly(name, y), lat, lon) for y in range(1970, 2101)]
        out[f"cordex_{name}"] = np.concatenate(parts) * k
        print("cordex", name, out[f"cordex_{name}"].shape, flush=True)
    (DATA / "sol").mkdir(exist_ok=True)
    np.savez_compressed(DATA / "sol" / "points.npz", **out)


if __name__ == "__main__":
    main()
