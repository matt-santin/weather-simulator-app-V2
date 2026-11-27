"""Essai : la ville dont le climat actuel ressemble le plus au climat futur d'un lieu.

Essai hors du site, pour décider si la fonction vaut d'être intégrée.

Grandeurs (12) : moyenne des minimales, moyenne des maximales et cumul de pluie
de chaque saison (DJF, MAM, JJA, SON), comme Fitzpatrick et Dunn 2019 (Nat.
Commun. 10, 614). Lues comme le site les sert (data/serve/point.zarr,
src.app.store : températures à 0,1° calées sur E-OBS, pluie à 0,25°).

Candidats : les villes de data/serve/places.tsv d'au moins MIN_POP habitants
dans l'emprise des données, climat 1991-2020 (données passées). Cible : le lieu
en 2041-2070 et en 2071-2100 (simulation corrigée).

Mise à l'échelle par la variabilité d'une année à l'autre du lieu cible
(1991-2020, données passées), comme Mahony et Cannon 2018 et Lotterhos et al.
2021 la décrivent pour la sigma dissimilarité de Mahony et al. 2017.
Variantes comparées :
  - diag     : chaque grandeur divisée par son écart-type interannuel (distance
               euclidienne standardisée, Williams et al. 2007), sans tendance ;
  - maha99   : Mahalanobis sur la covariance interannuelle, grandeurs
               standardisées puis composantes principales gardées jusqu'à 99 %
               de la variance (de la matrice de corrélation), sans tendance ;
  - maha99t  : la même, tendance linéaire de 1991-2020 retirée avant la covariance ;
  - diag_log : comme diag, pluie en log(1 + mm).
Distance en sigmas : rang du carré de la distance dans la loi du chi² à nu
degrés de liberté (nombre de grandeurs ou de composantes gardées), exprimé en
écarts-types d'une loi normale (2 sigmas : 95e centile, 4 : 99,994e).

    ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/analogues_essai.py
Écrit figures/climat/analogues_essai.txt.
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.app.store import Store  # noqa: E402
from src.config import DATA  # noqa: E402

OUT = Path(__file__).with_suffix(".txt")
MIN_POP = 100_000
REFERENCE = (1991, 2020)
FUTURES = [(2041, 2070), (2071, 2100)]
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}
NAMES = [f"{v} {s}" for s in SEASONS for v in ("Tn", "Tx", "P")]
TARGETS = [("Paris", 48.857, 2.352), ("Londres", 51.507, -0.128), ("Madrid", 40.417, -3.704),
           ("Stockholm", 59.329, 18.069), ("Berlin", 52.520, 13.405), ("Grenoble", 45.188, 5.725),
           ("Brest", 48.390, -4.486), ("Lyon", 45.764, 4.836), ("Bordeaux", 44.838, -0.579),
           ("Strasbourg", 48.573, 7.752), ("Rome", 41.893, 12.483), ("Moscou", 55.756, 37.617),
           ("Varsovie", 52.230, 21.012), ("Lisbonne", 38.722, -9.139), ("Athènes", 37.984, 23.728),
           ("Édimbourg", 55.953, -3.188)]


def seasonal(store: Store, source: str, cell, first: int, last: int) -> np.ndarray:
    """(years, 12): Tn, Tx, P of each season of each year first..last; DJF counted on its January."""
    start, end = date(first - 1, 12, 1), date(last, 11, 30)
    v = store.values(source, cell, start, end, ("tasmin", "tasmax", "pr"))
    days = np.arange(np.datetime64(start), np.datetime64(end) + 1)
    month = days.astype("datetime64[M]").astype(int) % 12 + 1
    year = days.astype("datetime64[Y]").astype(int) + 1970
    year = np.where(month == 12, year + 1, year)
    out = np.full((last - first + 1, 12), np.nan)
    for y in range(first, last + 1):
        for s, months in enumerate(SEASONS.values()):
            at = (year == y) & np.isin(month, months)
            out[y - first, 3 * s] = np.nanmean(v["tasmin"][at])
            out[y - first, 3 * s + 1] = np.nanmean(v["tasmax"][at])
            out[y - first, 3 * s + 2] = np.nansum(v["pr"][at])
    return out


def sigma(d2: np.ndarray, nu: int) -> np.ndarray:
    """Squared distance to sigmas: same two-sided mass of a standard normal as the chi² rank."""
    tail = stats.chi2.sf(d2, nu)
    return stats.norm.isf(np.clip(tail, 1e-300, 1) / 2)


def detrend(x: np.ndarray) -> np.ndarray:
    t = np.arange(x.shape[0]) - (x.shape[0] - 1) / 2
    slope = (t[:, None] * (x - x.mean(0))).sum(0) / (t**2).sum()
    return x - np.outer(t, slope)


def distances(variant: str, icv: np.ndarray, target: np.ndarray, candidates: np.ndarray):
    """Sigma of every candidate (n, 12) from the target (12,), and nu."""
    logp = variant.endswith("_log")
    if logp:
        P = slice(2, 12, 3)
        icv, target, candidates = icv.copy(), target.copy(), candidates.copy()
        for a in (icv, candidates):
            a[..., P] = np.log1p(a[..., P])
        target[P] = np.log1p(target[P])
    base = detrend(icv) if variant.endswith("t") else icv
    diff = candidates - target
    if variant.startswith("diag"):
        sd = base.std(0, ddof=1)
        d2 = ((diff / sd) ** 2).sum(1)
        return sigma(d2, diff.shape[1]), diff.shape[1]
    # Standardized first: the share of variance is then that of the correlation
    # matrix, not dominated by the rain in mm² (first version of this essay).
    sd = base.std(0, ddof=1)
    base, diff = base / sd, diff / sd
    cov = np.cov(base, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    k = int(np.searchsorted(np.cumsum(vals) / vals.sum(), 0.99) + 1)
    z = diff @ vecs[:, :k] / np.sqrt(vals[:k])
    d2 = (z**2).sum(1)
    return sigma(d2, k), k


def km(la1, lo1, la2, lo2) -> float:
    p1, p2, dl = map(math.radians, (la1, la2, lo2 - lo1))
    return 6371 * math.acos(min(1, math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)))


def main() -> None:
    store = Store()
    towns, seen = [], set()
    with open(DATA / "serve" / "places.tsv") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if int(row["population"]) < MIN_POP:
                continue
            la, lo = float(row["latitude"]), float(row["longitude"])
            cell = store.cell(la, lo)
            if cell is None or (cell.coarse, cell.fine) in seen:
                continue
            # Districts and suburbs: kept only the largest town within 15 km (the file is sorted by population).
            if any(km(la, lo, t[1], t[2]) < 15 for t in towns):
                continue
            seen.add((cell.coarse, cell.fine))
            towns.append((row["name"], la, lo, row["country"], cell))
    print(f"{len(towns)} villes candidates (>= {MIN_POP} hab.)", flush=True)
    present = np.array([seasonal(store, "era5", c, *REFERENCE).mean(0) for *_, c in towns])
    ok = np.isfinite(present).all(1)
    towns = [t for t, keep in zip(towns, ok) if keep]
    present = present[ok]
    print(f"{len(towns)} avec un climat 1991-2020 complet", flush=True)

    variants = ["diag", "maha99t"]
    lines = [f"Essai de villes analogues, {len(towns)} villes candidates (>= {MIN_POP} habitants), "
             f"climat 1991-2020 ; cible en 2041-2070 et 2071-2100 (simulation corrigée).", ""]
    for name, la, lo in TARGETS:
        cell = store.cell(la, lo)
        icv = seasonal(store, "era5", cell, *REFERENCE)
        own = icv.mean(0)
        lines.append(f"== {name}")
        for first, last in FUTURES:
            future = seasonal(store, "cordex", cell, first, last).mean(0)
            change = future - own
            lines.append(f"  {first}-{last} : Tn DJF {change[0]:+.1f} °C, Tx JJA {change[7]:+.1f} °C, "
                         f"P JJA {100 * change[8] / own[8]:+.0f} %, P DJF {100 * change[2] / own[2]:+.0f} %")
            for variant in variants:
                s, nu = distances(variant, icv, future, present)
                best = np.argsort(s)[:3]
                text = " ; ".join(
                    f"{towns[i][0]} ({towns[i][3]}, {s[i]:.1f}σ, {km(la, lo, towns[i][1], towns[i][2]):.0f} km)"
                    for i in best)
                lines.append(f"    {variant:9} nu={nu:2d} : {text}")
                # The nearest town among the good analogues: under 1 sigma, else 2, else the best.
                far = np.array([km(la, lo, t[1], t[2]) for t in towns])
                for limit in (1.0, 2.0, np.inf):
                    good = np.flatnonzero(s < limit) if np.isfinite(limit) else np.array([int(np.argmin(s))])
                    if good.size:
                        i = good[np.argmin(far[good])]
                        lines.append(f"    {'':9}       la plus proche sous {limit:g}σ : {towns[i][0]} "
                                     f"({towns[i][3]}, {s[i]:.1f}σ, {far[i]:.0f} km)")
                        break
        lines.append("")
        print("\n".join(lines[-12:]), flush=True)
    OUT.write_text("\n".join(lines))
    print("écrit", OUT)


if __name__ == "__main__":
    main()
