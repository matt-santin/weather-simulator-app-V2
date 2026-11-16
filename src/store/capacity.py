"""The available water of the soil, cell by cell, for the soil water balance.

    python -m src.store.capacity

Writes to the point store (data/serve/point.zarr), at the root, on the 0.25 deg
grid: `soil_capacity`, the size of the reservoir in mm, and
`soil_capacity_source`, where it comes from (1 ESDAC, 2 Stocker, 0 none: the
site then takes thresholds.SOIL_CAPACITY_MM). Then rebuild the map
(python -m src.store.soil).

- ESDAC (chosen 2026-11-16): European Soil Database Derived data (Hiederer
  2013, doi:10.2788/94128), total available water content from the HYPRES
  pedotransfer functions on the mapped soil typological units, topsoil
  (STU_EU_T_TAWC) plus subsoil (STU_EU_S_TAWC): water between -100 cm and
  -15 000 cm of pressure head, from 0 to 30 cm and from 30 cm to at most
  100 cm, both limited by the depth of the soil (p. 41). 1 km rasters in
  ETRS89-LAEA (EPSG:3035); a cell of 0.25 deg takes the mean of its 1 km cells
  that have a soil (a 0 is no soil described: sea, water bodies). Outside the
  European Soil Database the values come from the HWSD. The licence forbids
  passing the data to third parties: the layer stays on our machines, and the
  site serves the water left in the soil, never the capacity itself.
- Stocker et al. 2023 (Nature Geoscience, doi:10.1038/s41561-023-01125-2;
  data doi:10.5281/zenodo.10885724, CC BY 4.0), cwdx80_forcing, 0.05 deg,
  where ESDAC has nothing: the mean of its cells in the 0.25 deg cell. It is
  the storage the real vegetation draws on (forests included), larger than a
  soil's available water: it only fills the few cells ESDAC leaves empty.

The source files stay out of the repository, in data/sol (esdac/brut,
stocker). Needs pyproj, at building only.
"""

from __future__ import annotations

import logging
import sys
import time

import numpy as np
import xarray as xr
import zarr

from src.config import DATA
from src.store.build import STORE

ESDAC = DATA / "sol" / "esdac" / "brut"
STOCKER = DATA / "sol" / "stocker" / "cwdx80_forcing.nc"
ROWS, COLS, X0, Y1, STEP = 4600, 5900, 1500000.0, 5500000.0, 1000.0  # the 1 km rasters (.RDC)
NONE, FROM_ESDAC, FROM_STOCKER = 0, 1, 2

log = logging.getLogger("capacity")
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")


def raster(name: str, dtype: str) -> np.ndarray:
    return np.fromfile(ESDAC / f"{name}.rst", dtype=dtype).reshape(ROWS, COLS)


def cells(lat: np.ndarray, lon: np.ndarray, glat: np.ndarray, glon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index of the 0.25 deg cell holding each point (flat), and whether it lies on the grid."""
    step = abs(lat[1] - lat[0])
    i = np.round((lat[0] - glat) / step).astype(int)
    j = np.round((glon - lon[0]) / step).astype(int)
    inside = (i >= 0) & (i < lat.size) & (j >= 0) & (j < lon.size)
    return np.where(inside, i * lon.size + j, 0), inside


def esdac(lat: np.ndarray, lon: np.ndarray, layers: dict[str, np.ndarray] | None = None) -> dict[str, np.ndarray]:
    """Means over the 1 km cells with a soil, per 0.25 deg cell: the available
    water (`capacity`) and any other ``layers`` given (1 km arrays), the
    number of those cells (`soil_cells`) and their share of the cell (`soil_share`)."""
    from pyproj import Transformer

    total = raster("STU_EU_T_TAWC", "<f4") + raster("STU_EU_S_TAWC", "<f4")
    layers = {"capacity": total, **(layers or {})}
    soil = total > 0
    to_geo = Transformer.from_crs("EPSG:3035", "EPSG:4326", always_xy=True)
    size = lat.size * lon.size
    sums = {key: np.zeros(size) for key in (*layers, "soil", "all")}
    x = X0 + STEP * (np.arange(COLS) + 0.5)
    for r0 in range(0, ROWS, 400):
        r1 = min(r0 + 400, ROWS)
        glon, glat = to_geo.transform(*np.meshgrid(x, Y1 - STEP * (np.arange(r0, r1) + 0.5)))
        k, inside = cells(lat, lon, glat, glon)
        k, on = k[inside], soil[r0:r1][inside]
        sums["all"] += np.bincount(k, minlength=size)
        sums["soil"] += np.bincount(k, weights=on, minlength=size)
        for key, grid in layers.items():
            sums[key] += np.bincount(k, weights=np.where(on, grid[r0:r1][inside], 0.0), minlength=size)
    shape = (lat.size, lon.size)
    n = sums["soil"].reshape(shape)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = {key: np.where(n > 0, sums[key].reshape(shape) / n, np.nan) for key in layers}
        out["soil_share"] = np.where(sums["all"].reshape(shape) > 0, n / sums["all"].reshape(shape), np.nan)
    out["soil_cells"] = n
    return out


def stocker(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Mean of the 0.05 deg cells of Stocker et al. in each 0.25 deg cell, NaN without one."""
    step = abs(lat[1] - lat[0])
    with xr.open_dataset(STOCKER) as ds:
        da = ds["cwdx80_forcing"].sel(lat=slice(lat.min() - step, lat.max() + step),
                                      lon=slice(lon.min() - step, lon.max() + step))
        values = da.values.astype("float64")
        glat, glon = np.meshgrid(da.lat.values, da.lon.values, indexing="ij")
    k, inside = cells(lat, lon, glat, glon)
    ok = inside & np.isfinite(values)
    size = lat.size * lon.size
    n = np.bincount(k[ok], minlength=size)
    total = np.bincount(k[ok], weights=values[ok], minlength=size)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, total / n, np.nan).reshape(lat.size, lon.size)


def main() -> int:
    t0 = time.time()
    root = zarr.open_group(STORE, mode="a")
    lat, lon = root["latitude"][:], root["longitude"][:]
    domain = root["domain"][:].astype(bool)
    soil = esdac(lat, lon)["capacity"]
    vegetation = stocker(lat, lon)
    source = np.where(np.isfinite(soil), FROM_ESDAC, np.where(np.isfinite(vegetation), FROM_STOCKER, NONE))
    source = np.where(domain, source, NONE).astype("uint8")
    capacity = np.where(source == FROM_ESDAC, soil, np.where(source == FROM_STOCKER, vegetation, np.nan))
    arr = root.create_array("soil_capacity", data=capacity.astype("float32"), overwrite=True)
    arr.attrs.update({"units": "mm", "sources": {
        "1": "ESDAC, European Soil Database Derived data, STU_EU_T_TAWC + STU_EU_S_TAWC (Hiederer 2013, "
             "doi:10.2788/94128); not to be passed to third parties",
        "2": "Stocker et al. 2023, cwdx80_forcing (doi:10.5281/zenodo.10885724, CC BY 4.0)"},
        "built": time.strftime("%Y-%m-%d %H:%M")})
    root.create_array("soil_capacity_source", data=source, overwrite=True)
    inside = domain
    log.info("reserve utile : %d mailles du domaine, ESDAC %d, Stocker %d, aucune %d ; mediane %.0f mm ; %.0f s",
             inside.sum(), (source == FROM_ESDAC).sum(), (source == FROM_STOCKER).sum(),
             (inside & (source == NONE)).sum(), np.nanmedian(capacity[inside]), time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
