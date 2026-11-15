"""Ramener les températures servies à l'altitude du lieu : essai sur Tx et Tn aux stations ECA&D, 1991-2020.

    PYTHONPATH=. python figures/altitude/temperatures.py            (après lire.py ; 1 min)

Écart (site - station) du Tn et du Tx moyens, hiver (déc.-fév.) et été (juin-août), par classe d'écart
d'altitude entre la maille du site et la station (dz = maille - station), pour :
  - brut : la maille que le site donne au lieu ;
  - gradient fixe : T + L x dz, L = 5 et 6,5 K/km ;
  - gradient par mois, Tx et Tn séparés : pente de l'écart selon dz, estimée sur une moitié des stations
    (tirage au hasard), appliquée à l'autre ;
  - voisine : parmi la maille du site et ses 8 voisines, celle dont l'altitude est la plus proche de la
    station ; seule, puis avec le gradient par mois sur le reste d'écart d'altitude.
Les statistiques portent sur la moitié de contrôle. Écrit data/altitude/gradients.npy (12 mois x Tx, Tn).
"""
import numpy as np
import pandas as pd

from src.config import ROOT

D = np.load(ROOT / "data" / "altitude" / "stations.npz", allow_pickle=True)  # noms des stations en objets
elev, galt, name, cn = D["elev"], D["galt"], D["name"].astype(str), D["cn"].astype(str)
days = pd.date_range("1991-01-01", "2020-12-31")
month = days.month.values
N = elev.size
VARS = ("tn", "tx")
SEASONS = {"hiver": (12, 1, 2), "été": (6, 7, 8)}
CLASSES = ((-3000, -300), (-300, -100), (-100, 100), (100, 300), (300, 3000))
MIN_DAYS = 300  # jours valides par mois du calendrier, sur 30 ans

# Écart moyen par mois du calendrier : B[v][station, maille, mois]
B = {}
for v in VARS:
    obs, grid = D[v], D["g" + v]
    out = np.full((N, 9, 12), np.nan, "float32")
    for m in range(12):
        sel = month == m + 1
        o = obs[:, sel]
        ok = np.isfinite(o)
        n = ok.sum(1)
        for c in range(9):
            g = grid[:, c, :][:, sel]
            both = ok & np.isfinite(g)
            nb = both.sum(1)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[:, c, m] = np.where(nb >= MIN_DAYS, np.where(both, g - o, 0).sum(1) / nb, np.nan)
    B[v] = out
    del obs, grid

dz = galt[:, 0] - elev                      # maille du site moins station (m)
near = np.nanargmin(np.abs(galt - elev[:, None]), axis=1)
dzn = galt[np.arange(N), near] - elev       # idem pour la voisine la plus proche en altitude
rng = np.random.default_rng(1)
cal = rng.random(N) < 0.5
ctl = ~cal

# Gradient par mois : pente de l'écart selon dz, moitié de calage, stations à moins de 1 000 m de leur maille.
G = np.zeros((12, 2))
for j, v in enumerate(VARS):
    for m in range(12):
        y = B[v][:, 0, m]
        k = cal & np.isfinite(y) & (np.abs(dz) < 1000)
        G[m, j] = -1000 * np.polyfit(dz[k], y[k], 1)[0]
np.save(ROOT / "data" / "altitude" / "gradients.npy", G)
print(f"{N} stations ; calage {cal.sum()}, contrôle {ctl.sum()} ; stations d'entrée d'E-OBS : {D['in_eobs'].sum()}")
print(f"écart d'altitude maille - station : médiane {np.median(dz):+.0f} m, |dz| >= 100 m : {(np.abs(dz) >= 100).sum()}, >= 300 m : {(np.abs(dz) >= 300).sum()}")
print(f"voisine plus proche en altitude : |dz| médian {np.median(np.abs(dz)):.0f} m -> {np.median(np.abs(dzn)):.0f} m ; parmi |dz| >= 300 m : {np.median(np.abs(dz[np.abs(dz) >= 300])):.0f} -> {np.median(np.abs(dzn[np.abs(dz) >= 300])):.0f} m")
print("\nGradient par mois (K/km), calé sur une moitié des stations :")
print("  mois   " + " ".join(f"{m:5d}" for m in range(1, 13)))
for j, v in enumerate(VARS):
    print(f"  {v:6s} " + " ".join(f"{g:5.1f}" for g in G[:, j]))


def variants(v):
    j = VARS.index(v)
    raw = B[v][:, 0, :]
    nb = B[v][np.arange(N), near, :]
    return {
        "brut": raw,
        "5 K/km": raw + 5.0 * dz[:, None] / 1000,
        "6,5 K/km": raw + 6.5 * dz[:, None] / 1000,
        "par mois": raw + G[None, :, j] * dz[:, None] / 1000,
        "voisine": nb,
        "voisine + par mois": nb + G[None, :, j] * dzn[:, None] / 1000,
    }


def season(x, months):
    return x[:, [m - 1 for m in months]].mean(1)


def table(title, mask):
    print(f"\n{title}")
    for v in VARS:
        V = variants(v)
        for sname, months in SEASONS.items():
            print(f"  {v} {sname} : écart moyen (écart absolu moyen) entre stations, K")
            print(f"    {'dz (m)':>14s} {'st.':>5s} " + " ".join(f"{k:>18s}" for k in V))
            for lo, hi in CLASSES + ((-3000, 3000),):
                sel = mask & (dz >= lo) & (dz < hi) & np.isfinite(season(V["brut"], months))
                if sel.sum() < 5:
                    continue
                cells = [f"{np.nanmean(season(x, months)[sel]):+6.2f} ({np.nanmean(np.abs(season(x, months)[sel])):4.2f})" for x in V.values()]
                label = "toutes" if (lo, hi) == (-3000, 3000) else f"{lo:+d} à {hi:+d}"
                print(f"    {label:>14s} {sel.sum():5d} " + " ".join(f"{c:>18s}" for c in cells))


table("Contrôle, toutes les stations", ctl)
table("Contrôle, stations à 800 m et plus", ctl & (elev >= 800))
table("Contrôle, stations hors des entrées d'E-OBS", ctl & ~D["in_eobs"])
table("Contrôle, mailles en repli (ERA5-Land)", ctl & ~D["eobs"])

print("\nExemples (calage ou contrôle) : altitude station / maille / voisine ; puis Tn hiver et Tx été : brut, 6,5 K/km, par mois, voisine, voisine + par mois")
for want in ("CHAMONIX", "SAENTIS", "BROCKEN", "ZUGSPITZE", "SONNBLICK", "PIC DU MIDI", "DAVOS", "SION", "BOURG-ST-MAURICE", "BRIANCON", "EMBRUN", "INNSBRUCK", "AOSTA", "ANDERMATT", "LE PUY", "ST-MORITZ", "SAMEDAN"):
    for k in np.nonzero(np.char.find(np.char.upper(name), want) >= 0)[0][:2]:
        out = []
        for v, months in (("tn", SEASONS["hiver"]), ("tx", SEASONS["été"])):
            V = variants(v)
            out.append(" ".join(f"{season(V[x], months)[k]:+5.1f}" for x in ("brut", "6,5 K/km", "par mois", "voisine", "voisine + par mois")))
        print(f"  {name[k][:22]:22s} {cn[k]} {elev[k]:5.0f} / {galt[k, 0]:5.0f} / {galt[k, near[k]]:5.0f} m | Tn hiver {out[0]} | Tx été {out[1]}")
