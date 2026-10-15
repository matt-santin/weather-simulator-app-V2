"""Temperature reference for the correction: E-OBS on the site grids, ERA5-Land or ERA5 where E-OBS lacks.

    python -m src.correction.reference stats 010      pass 1: completeness, gaps, mask, map
    python -m src.correction.reference write 010      pass 2: yearly reference files
    (025 for the 0.25 deg grid)

Run from the repo root, with the external drive plugged in. Decided on
2026-10-11 (docs/correction.md, section 11): tas, tasmax and tasmin of the
model are corrected against E-OBS v33.0e (ensemble mean) instead of ERA5-Land
(0.1 deg) and ERA5 (0.25 deg). E-OBS is for non-commercial use only.

Grids: 010 is the ERA5-Land grid (from E-OBS 0.1 deg, fallback ERA5-Land
t2mmax, t2mmin, t2m), 025 the ERA5 grid (from E-OBS 0.25 deg, fallback ERA5
mx2t, mn2t, t2m). E-OBS centres sit half a cell off the site ones: bilinear
weights, kept on the valid E-OBS neighbours only and renormalised, so a cell
needs one valid neighbour (coastal cells are kept).

Mask, one per grid, the same for the three variables and the whole period,
past and future: E-OBS where it has a value on at least COMPLETE of the days
of YEARS for all three variables, outside FALLBACK_AREA (North Africa and the
Near East: E-OBS networks broken or gone, src.validation.eobs_era5land), on land
(at 0.25 deg, ERA5 land-sea mask >= 0.5); the fallback elsewhere. At 0.1 deg only cells with ERA5-Land (land) are written.
The rare days without E-OBS in an E-OBS cell take the fallback plus the mean
gap E-OBS - fallback of that cell and calendar month (pass 1).

Outputs on the external drive, in K: eobs/ref_<grid>/<name>_ref_day_<year>.nc,
the mask in eobs/ref_<grid>/source.nc (1 E-OBS, 0 fallback); pass 1 tables
and the mask map in data/correction/mpi/eobs_ref/.
"""

import logging
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.path import Path as Polygon

from src.config import ARCHIVE, DATA
from src.correction.qdm010 import land_file

YEARS = range(1970, 2026)
COMPLETE = 0.99
BLOCK = 92  # days remapped at once
NAMES = {"tasmax": ("tx", "t2mmax", "mx2t"), "tasmin": ("tn", "t2mmin", "mn2t"), "tas": ("tg", "t2m", "t2m")}
EOBS = ARCHIVE / "eobs"
ERA5 = ARCHIVE / "era5" / "daily"
WORK = DATA / "correction" / "mpi" / "eobs_ref"
# North Africa and the Near East (lon, lat), drawn through the sea between them and Europe:
# Western Sahara in; Canaries, Madeira, Sicily, Pantelleria, Lampedusa, Malta, Crete, Cyprus stay out; Hatay (Turkey) is in.
FALLBACK_AREA = Polygon([
    (-20.0, 21.0), (-20.0, 27.5), (-13.0, 27.5), (-13.2, 29.3), (-10.2, 31.5), (-9.5, 33.5), (-6.5, 35.95), (-5.0, 35.97),
    (-4.0, 36.0), (-2.0, 36.2), (0.0, 36.5), (3.0, 37.2), (8.0, 37.4), (10.0, 37.6), (11.3, 37.3),
    (12.3, 35.0), (15.0, 33.8), (20.0, 33.0), (25.0, 32.6), (29.0, 31.6), (32.0, 31.7), (34.2, 31.6),
    (35.0, 35.0), (35.9, 35.85), (36.6, 36.2), (36.7, 36.8), (38.0, 36.85), (40.0, 36.75), (41.3, 37.1),
    (42.4, 37.35), (75.0, 37.35), (75.0, 21.0)])

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO, datefmt="%H:%M:%S")
log = logging.getLogger("eobs_ref")


def out_dir(grid):
    return EOBS / f"ref_{grid}"


def ref_file(grid, name, year):
    return out_dir(grid) / f"{name}_ref_day_{year}0101-{year}1231.nc"


def fallback(grid, name, year):
    _, land, era5 = NAMES[name]
    if grid == "010":
        return xr.open_dataset(land_file(land, year))[land]
    return xr.open_dataset(ERA5 / f"{era5}_ERA5_day_{year}0101-{year}1231.nc")[era5]


class Remap:
    """E-OBS onto a site grid, bilinear on the valid neighbours."""

    def __init__(self, grid):
        self.grid = grid
        res = "0.1deg/" if grid == "010" else ""
        step = "0.1" if grid == "010" else "0.25"
        self.files = {n: EOBS / f"{res}{e}_ens_mean_{step}deg_reg_v33.0e.nc" for n, (e, _, _) in NAMES.items()}
        t = fallback(grid, "tas", 1970)
        self.lat, self.lon = t.latitude.values, t.longitude.values
        e = xr.open_dataset(self.files["tas"])
        elat, elon = e.latitude.values, e.longitude.values
        self.ilat = np.flatnonzero((self.lat >= elat[0]) & (self.lat <= elat[-1]))
        self.ilon = np.flatnonzero((self.lon >= elon[0]) & (self.lon <= elon[-1]))
        la, lo = self.lat[self.ilat], self.lon[self.ilon]
        self.i0 = np.clip(np.searchsorted(elat, la) - 1, 0, elat.size - 2)
        self.j0 = np.clip(np.searchsorted(elon, lo) - 1, 0, elon.size - 2)
        self.wy = ((la - elat[self.i0]) / (elat[self.i0 + 1] - elat[self.i0]))[:, None]
        self.wx = ((lo - elon[self.j0]) / (elon[self.j0 + 1] - elon[self.j0]))[None, :]
        lon2, lat2 = np.meshgrid(self.lon, self.lat)
        self.area = FALLBACK_AREA.contains_points(np.c_[lon2.ravel(), lat2.ravel()]).reshape(lat2.shape)

    def year(self, name, year):
        """E-OBS of the year on the site grid, K, NaN where no valid neighbour; (days, lat, lon)."""
        da = xr.open_dataset(self.files[name])[NAMES[name][0]].sel(time=str(year))
        out = np.full((da.time.size, self.lat.size, self.lon.size), np.nan, np.float32)
        a, b = self.i0[:, None], self.j0[None, :]
        w = [(1 - self.wy) * (1 - self.wx), self.wy * (1 - self.wx), (1 - self.wy) * self.wx, self.wy * self.wx]
        sub = np.ix_(self.ilat, self.ilon)
        for t in range(0, da.time.size, BLOCK):
            x = da.isel(time=slice(t, t + BLOCK)).values
            num = np.zeros((x.shape[0],) + self.wy.shape[:1] + self.wx.shape[1:], np.float32)
            den = np.zeros_like(num)
            for wk, (di, dj) in zip(w, ((0, 0), (1, 0), (0, 1), (1, 1))):
                v = x[:, a + di, b + dj]
                ok = np.isfinite(v)
                num += np.where(ok, v, 0) * wk
                den += ok * wk
            with np.errstate(invalid="ignore", divide="ignore"):
                block = np.where(den > 0, num / den, np.nan) + 273.15
            out[t:t + block.shape[0]][(slice(None),) + sub] = block
        return out


def stats(grid):
    """Pass 1: per cell, days with E-OBS; per cell and month, mean gap E-OBS - fallback; then the mask."""
    WORK.mkdir(parents=True, exist_ok=True)
    r = Remap(grid)
    shape = (r.lat.size, r.lon.size)
    tables = {}
    for name in NAMES:
        path = WORK / f"stats_{grid}_{name}.npz"
        if path.exists():
            tables[name] = dict(np.load(path))
            continue
        n_eobs = np.zeros(shape, np.int32)
        n_days = 0
        gap = np.zeros((12,) + shape)
        n_gap = np.zeros((12,) + shape, np.int32)
        valid = np.zeros(shape, bool)
        for y in YEARS:
            t0 = time.time()
            e = r.year(name, y)
            fb = fallback(grid, name, y)
            f = fb.values
            month = fb.time.dt.month.values
            n_eobs += np.isfinite(e).sum(0)
            n_days += e.shape[0]
            valid |= np.isfinite(f).any(0)
            d = e - f
            for m in range(1, 13):
                dm = d[month == m]
                ok = np.isfinite(dm)
                gap[m - 1] += np.where(ok, dm, 0).sum(0)
                n_gap[m - 1] += ok.sum(0)
            log.info("%s %s %d : %.0f s", grid, name, y, time.time() - t0)
        with np.errstate(invalid="ignore"):
            g = (gap / n_gap).astype(np.float32)
        tables[name] = {"frac": n_eobs / n_days, "gap": g, "valid": valid}
        np.savez(path, **tables[name])
    complete = np.all([tables[n]["frac"] >= COMPLETE for n in NAMES], 0)
    gaps_ok = np.all([np.isfinite(tables[n]["gap"]).all(0) for n in NAMES], 0)
    valid = tables["tas"]["valid"]
    use = complete & gaps_ok & ~r.area & valid
    if grid == "025":  # sea cells keep ERA5: E-OBS there would be land values carried offshore
        lsm = xr.open_dataarray(ARCHIVE / "era5" / "fixed" / "lsm_ERA5.nc").sel(latitude=r.lat, longitude=r.lon)
        use &= np.squeeze(lsm.values) >= 0.5
    source = np.where(valid, use.astype(np.float32), np.nan)
    out_dir(grid).mkdir(parents=True, exist_ok=True)
    xr.Dataset({"source": (("latitude", "longitude"), source)},
               coords={"latitude": r.lat, "longitude": r.lon},
               attrs={"source": "1: E-OBS v33.0e (ensemble mean), 0: " +
                                ("ERA5-Land" if grid == "010" else "ERA5"),
                      "rule": f"E-OBS on >= {COMPLETE:.0%} of the days {YEARS[0]}-{YEARS[-1]} for tx, tn and tg, "
                              "outside North Africa and the Near East"}).to_netcdf(out_dir(grid) / "source.nc")
    for name in NAMES:
        np.save(WORK / f"gap_{grid}_{name}.npy", tables[name]["gap"])

    fig, ax = plt.subplots(figsize=(11, 8))
    land = valid if grid == "010" else valid & (np.squeeze(lsm.values) >= 0.5)
    shown = np.where(land, np.where(use, 2, np.where(r.area, 0, 1)), np.nan)
    ax.pcolormesh(r.lon, r.lat, shown, cmap=matplotlib.colors.ListedColormap(["#eb6834", "#f2c14e", "#2a78d6"]),
                  vmin=-0.5, vmax=2.5, shading="nearest", rasterized=True)
    ax.plot(*FALLBACK_AREA.vertices.T, color="black", lw=0.6)
    ax.set_xlim(r.lon.min(), r.lon.max())
    ax.set_ylim(r.lat.min(), r.lat.max())
    ax.set_aspect(1 / np.cos(np.deg2rad(50)))
    ax.set_facecolor("#e8e8e8")
    n_use, n_area, n_inc = (int(x.sum()) for x in (use, land & r.area, land & ~use & ~r.area))
    ax.set_title(f"Reference des temperatures, grille {grid} : bleu E-OBS ({n_use} mailles), "
                 f"orange repli zone Afrique du Nord / Proche-Orient ({n_area}), "
                 f"jaune repli E-OBS incomplet ({n_inc}) ; terres seulement", fontsize=9)
    fig.tight_layout()
    fig.savefig(WORK / f"masque_{grid}.png", dpi=110)
    plt.close(fig)
    lines = [f"Grille {grid} : {int(land.sum())} mailles terre ; E-OBS {n_use}, "
             f"repli zone {n_area}, repli E-OBS incomplet {n_inc}"]
    for name in NAMES:
        g = tables[name]["gap"][:, use]
        lines.append(f"  {name} : ecart moyen E-OBS - repli sur les mailles E-OBS, par mois : "
                     + " ".join(f"{x:+.2f}" for x in np.nanmean(g, 1)))
    (WORK / f"stats_{grid}.log").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def write(grid):
    """Pass 2: yearly reference files."""
    r = Remap(grid)
    use = xr.open_dataset(out_dir(grid) / "source.nc").source.values == 1
    for name in NAMES:
        gap = np.load(WORK / f"gap_{grid}_{name}.npy")
        filled = 0
        for y in YEARS:
            path = ref_file(grid, name, y)
            if path.exists():
                continue
            t0 = time.time()
            fb = fallback(grid, name, y)
            f = fb.values
            e = r.year(name, y)
            month = fb.time.dt.month.values
            hole = use & ~np.isfinite(e)
            filled += int(hole.sum())
            e = np.where(hole, f + gap[month - 1], e)
            x = np.where(use, e, f).astype(np.float32)
            da = xr.DataArray(x, coords=fb.coords, dims=fb.dims, name=name,
                              attrs={"units": "K", "source": f"E-OBS v33.0e {NAMES[name][0]} (ensemble mean) where "
                                     f"source.nc is 1, else {fb.name} of " + ("ERA5-Land" if grid == "010" else "ERA5")})
            part = path.with_suffix(".part")
            da.to_netcdf(part, encoding={name: {"zlib": True, "complevel": 4}})
            part.rename(path)
            log.info("%s %s %d ecrit en %.0f s", grid, name, y, time.time() - t0)
        log.info("%s %s : %d valeurs E-OBS manquantes comblees par le repli + ecart moyen du mois", grid, name, filled)


if __name__ == "__main__":
    {"stats": stats, "write": write}[sys.argv[1]](sys.argv[2])
