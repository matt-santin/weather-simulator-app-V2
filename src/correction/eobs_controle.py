"""Checks of the temperatures corrected against E-OBS, at 0.1 deg (step 4).

    WSA_MODEL=mpi python -m src.correction.eobs_controle alpes
    WSA_MODEL=mpi python -m src.correction.eobs_controle humide
    WSA_MODEL=mpi python -m src.correction.eobs_controle raccords

External drive plugged in. Three corrections side by side: raw (remapped),
"ancien" (QDM against ERA5-Land, <model>_010_qdm), "E-OBS" (QDM against the
E-OBS reference, <model>_010_qdm_eobs).

alpes: Alps box, mean Tn of DJF and mean Tx of JJA over 1991-2014 (inside the
    calibration) and 2071-2100, per class of E-OBS altitude (nearest E-OBS
    cell): reference, raw, ancien, E-OBS. The past gap to the reference says
    whether the correction follows it up to the crests; the future gap E-OBS -
    ancien says whether the calibration offset carries over. Map of E-OBS -
    ancien, DJF Tn, 1991-2014, with the 1000 and 2000 m contours.
humide: mainland France, daily mean wet bulb (Stull 2011, as the site:
    src.app.domain.humidity) from tas at 0.1 deg and hurs at 0.25 deg (the
    0.25 cell holding the 0.1 cell, corrected against ERA5, unchanged), ancien
    against E-OBS: days per year at or above HUMID_HEAT_C and
    HUMID_HEAT_EXTREME_C, mean over cells, and the highest value.
raccords: seams where the reference switches between E-OBS and ERA5-Land
    (eobs/ref_010/source.nc). Climatology 1991-2014 of DJF Tn and JJA Tx;
    for each pair of adjacent land cells, the jump between them. Pairs that
    cross the switch against pairs that do not, for E-OBS and for ancien (no
    switch there): a seam shows as an extra jump on crossing pairs. Map of
    E-OBS - ancien, JJA Tx, whole domain, with the switch line.
Outputs: data/correction/mpi/eobs/controle_<command>.log, .png
"""

import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.path import Path as Polygon

from src.app.domain.thresholds import HUMID_HEAT_C, HUMID_HEAT_EXTREME_C
from src.config import ARCHIVE, ROOT
from src.correction.models import MODEL

warnings.filterwarnings("ignore", category=RuntimeWarning)
CORDEX = ARCHIVE / "cordex"
SOURCES = {"brut": CORDEX / f"{MODEL.out}_010", "ancien": CORDEX / f"{MODEL.out}_010_qdm",
           "E-OBS": CORDEX / f"{MODEL.out}_010_qdm_eobs"}
REF = ARCHIVE / "eobs" / "ref_010"
HURS = CORDEX / f"{MODEL.out}_025_qdm"
ELEV = ARCHIVE / "eobs" / "0.1deg" / "elev_ens_0.1deg_reg_v33.0e.nc"
OUT = ROOT / "data" / "correction" / MODEL.tables / "eobs"
PAST, FUTURE = range(1991, 2015), range(2071, 2101)
SEASONS = {"tasmin": ("Tn DJF", (12, 1, 2)), "tasmax": ("Tx JJA", (6, 7, 8))}
ALPS = dict(latitude=slice(48.5, 43.5), longitude=slice(5.0, 17.0))
FRANCE = dict(latitude=slice(51.2, 41.3), longitude=slice(-5.2, 9.6))
ALTITUDES = [(-500, 500), (500, 1000), (1000, 1500), (1500, 2000), (2000, 5000)]


def path(source, name, year):
    if source == "ref":
        return REF / f"{name}_ref_day_{year}0101-{year}1231.nc"
    return next(SOURCES[source].glob(f"{name}_*_day_{year}0101-{year}1231.nc"))


def seasonal(source, name, years, box=None):
    """Mean over the season of `name` and the years, deg C, (lat, lon)."""
    months = SEASONS[name][1]
    total, n = 0, 0
    for y in years:
        da = xr.open_dataset(path(source, name, y))[name]
        if box:
            da = da.sel(**box)
        da = da.sel(time=da.time.dt.month.isin(months))
        total = total + da.sum("time").values
        n += da.sizes["time"]
    return total / n - 273.15, da


def altitude(da):
    e = xr.open_dataset(ELEV).elevation
    return e.sel(latitude=da.latitude, longitude=da.longitude, method="nearest").values


def alpes():
    lines = [f"Alpes ({ALPS['latitude'].stop}-{ALPS['latitude'].start} N, "
             f"{ALPS['longitude'].start}-{ALPS['longitude'].stop} E), moyennes en deg C par classe d'altitude E-OBS"]
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    for k, name in enumerate(SEASONS):
        label = SEASONS[name][0]
        past = {s: seasonal(s, name, PAST, ALPS)[0] for s in ("brut", "ancien", "E-OBS")}
        ref, da = seasonal("ref", name, PAST, ALPS)
        fut = {s: seasonal(s, name, FUTURE, ALPS)[0] for s in ("ancien", "E-OBS")}
        z = altitude(da)
        lines += ["", f"{label}, {PAST[0]}-{PAST[-1]} : reference E-OBS, puis ecart a la reference ; "
                      f"{FUTURE[0]}-{FUTURE[-1]} : E-OBS - ancien",
                  "altitude   | mailles | reference | brut   | ancien | E-OBS  | futur E-OBS - ancien | passe E-OBS - ancien"]
        for lo, hi in ALTITUDES:
            sel = np.isfinite(ref) & np.isfinite(past["E-OBS"]) & (z >= lo) & (z < hi)
            if sel.sum() < 10:
                continue
            gap = {s: np.nanmean(past[s][sel] - ref[sel]) for s in past}
            lines.append(f"{lo:5d}-{hi:<5d}| {sel.sum():7d} | {np.nanmean(ref[sel]):9.2f} | {gap['brut']:+6.2f} | "
                         f"{gap['ancien']:+6.2f} | {gap['E-OBS']:+6.2f} | "
                         f"{np.nanmean(fut['E-OBS'][sel] - fut['ancien'][sel]):+20.2f} | "
                         f"{np.nanmean(past['E-OBS'][sel] - past['ancien'][sel]):+.2f}")
        d = past["E-OBS"] - past["ancien"]
        ax = axes[k]
        m = ax.pcolormesh(da.longitude, da.latitude, d, vmin=-5, vmax=5, cmap="RdBu_r")
        ax.contour(da.longitude, da.latitude, z, levels=[1000, 2000], colors=["0.4", "k"], linewidths=0.6)
        ax.set_title(f"{label} {PAST[0]}-{PAST[-1]}, E-OBS - ancien (K) ; contours 1000 et 2000 m")
        fig.colorbar(m, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "controle_alpes.png", dpi=110)
    return lines


def france_mask(lat, lon):
    g = json.load(open(ROOT / "data" / "fixed" / "ne_50m_admin_0_countries.geojson"))
    geom = next(f for f in g["features"] if f["properties"].get("ADM0_A3") == "FRA")["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    lo, la = np.meshgrid(lon, lat)
    pts = np.c_[lo.ravel(), la.ravel()]
    m = np.zeros(len(pts), bool)
    for p in polys:
        ring = np.array(p[0])
        if ring[:, 0].min() >= -10 and ring[:, 1].min() >= 40:  # mainland and Corsica
            m |= Polygon(ring).contains_points(pts)
    return m.reshape(lo.shape)


def stull(t, rh):
    rh = np.minimum(rh, 100.0)
    w = (t * np.arctan(0.151977 * np.sqrt(rh + 8.313659)) + np.arctan(t + rh) - np.arctan(rh - 1.676331)
         + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh) - 4.686035)
    return np.minimum(w, t)


def humide():
    lines = [f"France metropolitaine, temperature humide moyenne du jour (Stull), tas 0,1 deg + hurs 0,25 deg ; "
             f"jours par an >= {HUMID_HEAT_C} et >= {HUMID_HEAT_EXTREME_C} deg C (moyenne des mailles), maximum"]
    mask = None
    for years in (range(1991, 2021), range(2041, 2071), range(2071, 2101)):
        res = {s: [0.0, 0.0, -99.0] for s in ("ancien", "E-OBS")}
        for y in years:
            h = xr.open_dataset(next(HURS.glob(f"hurs_*_day_{y}0101-{y}1231.nc"))).hurs
            for s in res:
                t = xr.open_dataset(path(s, "tas", y)).tas.sel(**FRANCE) - 273.15
                if mask is None:
                    mask = france_mask(t.latitude.values, t.longitude.values)
                rh = h.sel(latitude=t.latitude, longitude=t.longitude, method="nearest").values
                w = stull(t.values[:, mask], rh[:, mask])
                res[s][0] += np.nanmean((w >= HUMID_HEAT_C).sum(0))
                res[s][1] += np.nanmean((w >= HUMID_HEAT_EXTREME_C).sum(0))
                res[s][2] = max(res[s][2], float(np.nanmax(w)))
        n = len(years)
        lines.append(f"{years[0]}-{years[-1]} : " + " | ".join(
            f"{s} {r[0] / n:6.3f} j/an, {r[1] / n:6.4f} j/an, max {r[2]:.1f}" for s, r in res.items()))
        print(lines[-1], flush=True)
    return lines


def raccords():
    src = xr.open_dataset(REF / "source.nc").source
    lines = ["Raccords E-OBS / ERA5-Land de la reference, climatologie 1991-2014, saut moyen entre mailles voisines (K)",
             "grandeur | paires | sans changement de source : E-OBS / ancien | a travers le changement : E-OBS / ancien | exces"]
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    for k, name in enumerate(SEASONS):
        clim = {s: seasonal(s, name, PAST)[0] for s in ("ancien", "E-OBS")}
        s = src.values
        jumps = {}
        for s_name, c in clim.items():
            for axis in (0, 1):
                a, b = (c[:-1], c[1:]) if axis == 0 else (c[:, :-1], c[:, 1:])
                sa, sb = (s[:-1], s[1:]) if axis == 0 else (s[:, :-1], s[:, 1:])
                ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(sa) & np.isfinite(sb)
                for cross in (False, True):
                    sel = ok & ((sa != sb) == cross)
                    jumps.setdefault((s_name, cross), []).append(np.abs(a - b)[sel])
        j = {key: np.concatenate(v) for key, v in jumps.items()}
        same = (j["E-OBS", False].mean(), j["ancien", False].mean())
        cross = (j["E-OBS", True].mean(), j["ancien", True].mean())
        lines.append(f"{SEASONS[name][0]} | {j['E-OBS', True].size:6d} | {same[0]:.3f} / {same[1]:.3f} | "
                     f"{cross[0]:.3f} / {cross[1]:.3f} | {(cross[0] - cross[1]) - (same[0] - same[1]):+.3f}")
        d = clim["E-OBS"] - clim["ancien"]
        ax = axes[k]
        m = ax.pcolormesh(src.longitude, src.latitude, d, vmin=-3, vmax=3, cmap="RdBu_r")
        ax.contour(src.longitude, src.latitude, np.nan_to_num(s, nan=-1), levels=[0.5], colors="k", linewidths=0.4)
        ax.set_title(f"{SEASONS[name][0]} {PAST[0]}-{PAST[-1]}, E-OBS - ancien (K) ; trait : limite E-OBS / ERA5-Land")
        fig.colorbar(m, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(OUT / "controle_raccords.png", dpi=110)
    return lines


def main(argv):
    commands = {"alpes": alpes, "humide": humide, "raccords": raccords}
    if len(argv) != 1 or argv[0] not in commands:
        print(__doc__)
        return 1
    lines = commands[argv[0]]()
    text = "\n".join(lines) + "\n"
    (OUT / f"controle_{argv[0]}.log").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
