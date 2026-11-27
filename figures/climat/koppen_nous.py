"""Köppen-Geiger calculé sur nos données, à 0,25°, et comparé à Beck et al. 2023.

Nos données : le stockage de service (data/serve/point.zarr), grille à 0,25°,
`tas` (température moyenne journalière, calée sur E-OBS) et `pr`.
  - ERA5 1991-2020 (le passé servi par le site) ;
  - MPI-ESM1-2-HR / ICON-CLM corrigé, SSP3-7.0 : 1991-2020, 2041-2070, 2071-2099
    (mêmes périodes que Beck ; 2071-2099 compte 29 ans chez Beck comme ici).
Par maille : température moyenne de chaque mois (moyenne des jours), précipitation
d'un mois moyen (moyenne journalière x longueur moyenne du mois), comme le
diagramme climatique du site (src/app/api/climate.py).

Critères : Beck et al. 2023, Sci. Data 10, 724, tableau 1 et méthodes
(texte intégral, Europe PMC, PMC10593765) :
  - B prioritaire sur A, C, D, E ; seuil Pthreshold = 2 MAT (+14, ou +28 si plus
    de 70 % des pluies tombent en été, +0 si plus de 70 % en hiver) ;
  - C / D séparés à 0 °C (C : 0 < Tcold < 18, D : Tcold <= 0) ;
  - été (hiver) : le plus chaud (froid) des deux semestres avril-septembre et
    octobre-mars ;
  - s et w exclusifs : s seulement si l'hiver est plus arrosé que l'été, w
    seulement dans le cas inverse.
Beck : cartes à 0,01° (data/koppen/beck2023), ramenées à 0,25° par la classe la
plus fréquente des pixels terrestres de chaque maille.

Écrit :
  - data/koppen/nous/koppen_025.nc : classes (numéros de la légende de Beck),
    moyennes mensuelles T et P pour les quatre périodes et masque des terres
    (mailles où Beck a des terres), à garder ; les classes couvrent tout le
    domaine, mer comprise ;
  - figures/climat/koppen_nous_vs_beck.png : nos classes, celles de Beck et
    l'accord, pour 1991-2020 (ERA5) et 2071-2099 (MPI / ICON) ;
  - web/static/img/koppen_comparaison.webp : la même figure pour la page de
    documentation du site ;
  - les taux d'accord et la classe de quelques villes, à l'écran.

    caffeinate -i ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/koppen_nous.py
"""
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path as P

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import zarr
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from PIL import Image

sys.path.insert(0, str(P(__file__).resolve().parents[2]))
from src.app.domain import koppen  # noqa: E402

ROOT = P(__file__).resolve().parents[2]
STORE = ROOT / "data" / "serve" / "point.zarr"
BECK = ROOT / "data" / "koppen" / "beck2023"
OUT_NC = ROOT / "data" / "koppen" / "nous" / "koppen_025.nc"
OUT_PNG = ROOT / "figures" / "climat" / "koppen_nous_vs_beck.png"
OUT_WEB = ROOT / "web" / "static" / "img" / "koppen_comparaison.webp"
EPOCH = date(1970, 1, 1)
INK, MUTED = "#0b0b0b", "#52514e"

# (identifiant, groupe du stockage, première année, dernière année, carte de Beck)
PERIODES = [
    ("era5_1991_2020", "era5", 1991, 2020, "1991_2020"),
    ("mpi_1991_2020", "cordex", 1991, 2020, "1991_2020"),
    ("mpi_2041_2070", "cordex", 2041, 2070, "2041_2070/ssp370"),
    ("mpi_2071_2099", "cordex", 2071, 2099, "2071_2099/ssp370"),
]
VILLES = [("Paris", 48.857, 2.352), ("Lyon", 45.764, 4.836), ("Bordeaux", 44.838, -0.579),
          ("Toulouse", 43.605, 1.444), ("Grenoble", 45.188, 5.725), ("Strasbourg", 48.573, 7.752),
          ("Brest", 48.390, -4.486), ("Marseille", 43.296, 5.370), ("Madrid", 40.417, -3.704),
          ("Berlin", 52.520, 13.405), ("Rome", 41.893, 12.483), ("Stockholm", 59.329, 18.069)]


def legende():
    """{numéro: (code, (r, g, b))} et {code: numéro}, lus dans legend.txt de Beck."""
    out = {}
    for line in (BECK / "legend.txt").read_text().splitlines():
        m = re.match(r"\s*(\d+):\s+(\w+)\s.*\[(\d+) (\d+) (\d+)\]", line)
        if m:
            out[int(m[1])] = (m[2], tuple(int(m[i]) / 255 for i in (3, 4, 5)))
    return out, {code: k for k, (code, _) in out.items()}


def classer(T, Pm, numero):
    """Classe (numéro de la légende de Beck) de chaque colonne, 0 là où une valeur manque.

    Le classement est celui du site, src/app/domain/koppen.py.
    """
    code = koppen.classify(T, Pm)
    return np.array([numero.get(str(c), 0) for c in code], dtype=np.uint8)


def moyennes(group, first, last, rows, mois, longueur):
    """T et P mensuels (12, lignes, colonnes) sur first..last, pour les lignes données."""
    i0, i1 = (date(first, 1, 1) - EPOCH).days, (date(last, 12, 31) - EPOCH).days + 1
    out = {}
    for name in ("tas", "pr"):
        a = group[name]
        raw = a[i0:i1, rows, :]
        fill, scale = a.attrs["_FillValue"], a.attrs["scale_factor"]
        v = np.where(raw == fill, np.nan, raw.astype(np.float32) * scale)
        out[name] = np.stack([np.nanmean(v[mois == m], axis=0) for m in range(1, 13)])
    out["pr"] = out["pr"] * longueur[:, None, None]
    return out["tas"], out["pr"]


def calendrier(first, last):
    n = (date(last, 12, 31) - date(first, 1, 1)).days + 1
    mois = np.array([(date(first, 1, 1) + timedelta(days=k)).month for k in range(n)])
    longueur = np.array([(mois == m).sum() / (last - first + 1) for m in range(1, 13)])
    return mois, longueur


def beck_025(chemin, lat, lon):
    """Classe la plus fréquente des pixels terrestres de Beck (0,01°) dans chaque maille à 0,25°."""
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(BECK / chemin / "koppen_geiger_0p01.tif")
    half = 0.125
    lat1, lon0 = lat.max() + half, lon.min() - half
    lat0, lon1 = lat.min() - half, lon.max() + half
    x0, y0 = round((lon0 + 180) / 0.01), round((90 - lat1) / 0.01)
    x1, y1 = round((lon1 + 180) / 0.01), round((90 - lat0) / 0.01)
    a = np.array(im.crop((x0, y0, x1, y1)))
    py = lat1 - 0.01 * (np.arange(a.shape[0]) + 0.5)
    px = lon0 + 0.01 * (np.arange(a.shape[1]) + 0.5)
    ii = np.clip(((lat1 - py) / 0.25).astype(int), 0, lat.size - 1)
    jj = np.clip(((px - lon0) / 0.25).astype(int), 0, lon.size - 1)
    cell = ii[:, None] * lon.size + jj[None, :]
    land = a > 0
    counts = np.bincount(cell[land] * 31 + a[land].astype(int), minlength=lat.size * lon.size * 31)
    counts = counts.reshape(lat.size * lon.size, 31)
    mode = counts.argmax(1).astype(np.uint8)
    mode[counts.sum(1) == 0] = 0
    return mode.reshape(lat.size, lon.size)


def calculer(z, lat, lon, domain):
    """Classes et moyennes des quatre périodes, bande de deux lignes par bande (un bloc du stockage)."""
    _, numero = legende()
    ny, nx = lat.size, lon.size
    T = {k: np.full((12, ny, nx), np.nan, np.float32) for k, *_ in PERIODES}
    Pm = {k: np.full((12, ny, nx), np.nan, np.float32) for k, *_ in PERIODES}
    cal = {(f, l): calendrier(f, l) for _, _, f, l, _ in PERIODES}
    t0 = time.time()
    for r in range(0, ny, 2):
        rows = slice(r, min(r + 2, ny))
        if not domain[rows].any():
            continue
        for key, group, first, last, _ in PERIODES:
            mois, longueur = cal[(first, last)]
            t, p = moyennes(z[group], first, last, rows, mois, longueur)
            T[key][:, rows] = t
            Pm[key][:, rows] = p
        if r % 20 == 0:
            done = (r + 2) / ny
            print(f"  lignes {r + 2}/{ny}, {time.time() - t0:.0f} s, reste environ "
                  f"{(time.time() - t0) / done * (1 - done) / 60:.0f} min", flush=True)
    classes = {}
    for key, *_ in PERIODES:
        c = classer(T[key].reshape(12, -1), Pm[key].reshape(12, -1), numero).reshape(ny, nx)
        c[~domain] = 0
        classes[key] = c
    return T, Pm, classes


def sauver(T, Pm, classes, lat, lon, terre):
    OUT_NC.parent.mkdir(parents=True, exist_ok=True)
    keys = [k for k, *_ in PERIODES]
    leg, _ = legende()
    ds = xr.Dataset(
        {
            "koppen": (("period", "latitude", "longitude"), np.stack([classes[k] for k in keys])),
            "tas": (("period", "month", "latitude", "longitude"), np.stack([T[k] for k in keys])),
            "pr": (("period", "month", "latitude", "longitude"), np.stack([Pm[k] for k in keys])),
            "land": (("latitude", "longitude"), terre.astype(np.uint8)),
        },
        coords={"period": keys, "month": np.arange(1, 13), "latitude": lat, "longitude": lon},
        attrs={
            "title": "Köppen-Geiger à 0,25° calculé sur le stockage de service (ERA5 1991-2020, MPI-ESM1-2-HR / ICON-CLM SSP3-7.0 corrigé)",
            "criteria": "Beck et al. 2023, Sci. Data 10, 724, tableau 1 (B prioritaire, C/D à 0 °C, s/w exclusifs)",
            "legend": "; ".join(f"{k}={leg[k][0]}" for k in sorted(leg)),
            "script": "figures/climat/koppen_nous.py",
        },
    )
    ds["tas"].attrs = {"units": "degC", "long_name": "température moyenne du mois"}
    ds["pr"].attrs = {"units": "mm", "long_name": "précipitation d'un mois moyen"}
    ds["koppen"].attrs = {"long_name": "classe de Köppen-Geiger, numéros de la légende de Beck, 0 hors domaine"}
    ds["land"].attrs = {"long_name": "1 si la maille contient des terres selon Beck et al. 2023 (0,01°)"}
    enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
    ds.to_netcdf(OUT_NC, encoding=enc)
    print("écrit", OUT_NC)


def accord(nous, beck, leg):
    """Taux d'accord sur les mailles classées des deux côtés : classe, deux lettres, grande famille."""
    m = (nous > 0) & (beck > 0)
    a, b = nous[m], beck[m]
    code = np.array([leg[k][0] if k else "" for k in range(31)], dtype=object)
    ca, cb = code[a], code[b]
    exact = (a == b).mean()
    deux = np.mean([x[:2] == y[:2] for x, y in zip(ca, cb)])
    une = np.mean([x[0] == y[0] for x, y in zip(ca, cb)])
    return m.sum(), exact, deux, une


def figure(classes, becks, lat, lon, leg):
    cmap = ListedColormap([(1, 1, 1)] + [leg[i][1] for i in range(1, 31)])
    gj = json.loads((ROOT / "data" / "fixed" / "ne_50m_admin_0_countries.geojson").read_text())
    pays = []
    for f in gj["features"]:
        g = f["geometry"]
        for poly in g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]:
            pays += [np.array(ring).T for ring in poly]
    ext = (lon.min() - 0.125, lon.max() + 0.125, lat.min() - 0.125, lat.max() + 0.125)
    code = np.array([leg[k][0] if k else "" for k in range(31)], dtype=object)
    lignes = [("era5_1991_2020", "1991-2020", "ERA5"), ("mpi_2071_2099", "2071-2099", "MPI / ICON, SSP3-7.0")]
    fig, axes = plt.subplots(2, 3, figsize=(20, 11.5))
    accord_cmap = ListedColormap(["#ffffff", "#2e8b57", "#e6b800", "#c0392b"])
    terre = becks["era5_1991_2020"] > 0
    for row, (key, periode, source) in enumerate(lignes):
        nous, beck = np.where(terre, classes[key], 0), becks[key]
        m = (nous > 0) & (beck > 0)
        etat = np.zeros_like(nous)
        same1 = np.vectorize(lambda x, y: x[:1] == y[:1])(code[nous], code[beck])
        etat[m] = np.where(nous[m] == beck[m], 1, np.where(same1[m], 2, 3))
        n, exact, deux, une = accord(nous, beck, leg)
        for col, (data, cm, vmax, titre) in enumerate([
            (nous, cmap, 30.5, f"Nos données, {periode} ({source})"),
            (beck, cmap, 30.5, f"Beck et al. 2023, {periode}" + (", SSP3-7.0" if row else "")),
            (etat, accord_cmap, 3.5, f"Accord : {100 * exact:.0f} % même classe, {100 * une:.0f} % même famille"),
        ]):
            ax = axes[row, col]
            ax.imshow(np.ma.masked_equal(data, 0), cmap=cm, vmin=-0.5, vmax=vmax, extent=ext,
                      interpolation="nearest", zorder=1)
            for x, y in pays:
                ax.plot(x, y, color=INK, lw=0.3, alpha=0.5, zorder=2)
            ax.set_xlim(-25, 45)
            ax.set_ylim(33, 72)
            ax.set_aspect(1 / np.cos(np.radians(52)))
            ax.set_facecolor("#dfe8ee")
            ax.tick_params(colors=MUTED, labelsize=7)
            ax.set_title(titre, loc="left", fontsize=11, color=INK)
    presentes = sorted({int(v) for c in classes.values() for v in np.unique(c) if v} |
                       {int(v) for c in becks.values() for v in np.unique(c) if v})
    poignees = [Patch(facecolor=leg[v][1], edgecolor=MUTED, lw=0.3, label=leg[v][0]) for v in presentes]
    poignees += [Patch(facecolor=c, label=l) for c, l in
                 (("#2e8b57", "même classe"), ("#e6b800", "même famille (1re lettre)"), ("#c0392b", "famille différente"))]
    fig.legend(handles=poignees, loc="lower center", ncol=min(len(poignees), 16), frameon=False, fontsize=8.5)
    fig.suptitle("Köppen-Geiger calculé sur nos données (0,25°) et Beck et al. 2023 (1 km ramené à 0,25°)",
                 x=0.01, ha="left", fontsize=14, color=INK)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(OUT_PNG, dpi=130, bbox_inches="tight")
    print("écrit", OUT_PNG)
    # La même, allégée, pour la page de documentation du site.
    OUT_WEB.parent.mkdir(parents=True, exist_ok=True)
    Image.open(OUT_PNG).convert("RGB").save(OUT_WEB, "WEBP", quality=82, method=6)
    print("écrit", OUT_WEB, f"{OUT_WEB.stat().st_size // 1024} ko")


def main():
    leg, _ = legende()
    z = zarr.open_group(STORE, mode="r")
    lat, lon = z["latitude"][:], z["longitude"][:]
    domain = z["domain"][:].astype(bool)
    print(f"grille {lat.size} x {lon.size}, {domain.sum()} mailles dans le domaine", flush=True)
    T, Pm, classes = calculer(z, lat, lon, domain)
    becks = {key: beck_025(chemin, lat, lon) for key, _, _, _, chemin in PERIODES}
    sauver(T, Pm, classes, lat, lon, becks["era5_1991_2020"] > 0)

    print("\nAccord avec Beck (mailles classées des deux côtés)")
    print(f"{'période':16} {'mailles':>8} {'classe':>7} {'2 lettres':>10} {'famille':>8}")
    for key, *_ in PERIODES:
        n, exact, deux, une = accord(classes[key], becks[key], leg)
        print(f"{key:16} {n:8d} {100 * exact:6.1f} % {100 * deux:8.1f} % {100 * une:6.1f} %")

    print("\nVille        " + "  ".join(f"{k:>14}" for k, *_ in PERIODES) + "   (nous / Beck)")
    for nom, la, lo in VILLES:
        i, j = int(np.abs(lat - la).argmin()), int(np.abs(lon - lo).argmin())
        cells = []
        for key, *_ in PERIODES:
            a, b = classes[key][i, j], becks[key][i, j]
            cells.append(f"{(leg[a][0] if a else '-') + ' / ' + (leg[b][0] if b else '-'):>14}")
        print(f"{nom:12} " + "  ".join(cells))
    figure(classes, becks, lat, lon, leg)


if __name__ == "__main__":
    sys.exit(main())
