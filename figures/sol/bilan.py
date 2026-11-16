"""Essai du bilan hydrique aux lieux de figures/sol/lire.py.

    python figures/sol/bilan.py [réserve utile en mm, 100 par défaut | stocker | esdac]

Avec « stocker », la réserve utile de chaque lieu est la moyenne, sur sa maille
de 0,25°, de la capacité de stockage de la zone racinaire de Stocker et al. 2023
(data/sol/stocker/cwdx80_forcing.nc, 0,05°). Avec « esdac », celle d'ESDAC ramenée sur
la maille par figures/sol/esdac.py (data/sol/esdac/reserve_025.nc).

Températures, pluie, humidité et vent : stockage de service (ce que sert le
site). Rayonnements et évaporation : data/sol/points.npz. ET0 de FAO-56 avec
deux rayonnements infrarouges nets (estimation FAO ; flux descendant du modèle
moins l'émission à la température de l'air), puis réservoir (src.app.domain.soil).
Sorties : tableaux à l'écran, figures dans figures/sol.
"""
import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.app.domain import et0, soil  # noqa: E402
from src.app.store import Store  # noqa: E402
from src.config import DATA  # noqa: E402

ARG = sys.argv[1] if len(sys.argv) > 1 else "100"
NAMED = {"stocker": "réserve utile de Stocker et al. 2023", "esdac": "réserve utile d'ESDAC (Hiederer 2013)"}
TAG = ARG if ARG in NAMED else f"{float(ARG):.0f}mm"
LABEL = NAMED.get(ARG) or f"réserve utile {float(ARG):.0f} mm"


def capacities(pts):
    """Réserve utile de chaque lieu, en mm."""
    import xarray as xr
    if ARG == "esdac":
        with xr.open_dataset(DATA / "sol" / "esdac" / "reserve_025.nc") as ds:
            return [float(ds.capacity.sel(latitude=la, longitude=lo, method="nearest"))
                    for la, lo in zip(pts["lat"], pts["lon"])]
    if ARG != "stocker":
        return [float(ARG)] * len(pts["lat"])
    with xr.open_dataset(DATA / "sol" / "stocker" / "cwdx80_forcing.nc") as ds:
        da = ds["cwdx80_forcing"]
        return [float(da.sel(lat=slice(la - 0.125, la + 0.125), lon=slice(lo - 0.125, lo + 0.125)).mean())
                for la, lo in zip(np.round(pts["lat"] * 4) / 4, np.round(pts["lon"] * 4) / 4)]

OUT = Path(__file__).parent
SPANS = {"era5": (date(1970, 1, 1), date(2025, 12, 31)), "cordex": (date(1970, 1, 1), date(2100, 12, 31))}
RAD = {"era5": ("ssrd", "strd", "e"), "cordex": ("rsds", "rlds", "evspsbl")}
NAMES = ("tasmax", "tasmin", "tas", "pr", "hurs", "sfcWind")


def compute(store, pts, k, source, capacity):
    """Séries journalières d'un lieu : dates, ET0 (deux variantes), bilan, pluie, évaporation du modèle."""
    start, end = SPANS[source]
    cell = store.cell(float(pts["lat"][k]), float(pts["lon"][k]))
    v = store.values(source, cell, start, end, NAMES)
    days = np.datetime64(start.isoformat()) + np.arange((end - start).days + 1)
    down, lw, evap = (pts[f"{source}_{n}"][:, k].astype(float) for n in RAD[source])
    assert len(down) == len(days), (source, len(down), len(days))
    alt = store.elevation(cell) or 0.0
    doy = (days - days.astype("datetime64[Y]")).astype(int) + 1
    rs = down * et0.MJ_PER_W
    es, ea = et0.vapour(v["tasmax"], v["tasmin"], v["hurs"])
    rso = et0.clear_sky(et0.extraterrestrial(float(pts["lat"][k]), doy), alt)
    rns = (1 - et0.ALBEDO) * rs
    rnl = {"fao": et0.net_longwave(v["tasmax"], v["tasmin"], ea, rs, rso),
           "flux": et0.SIGMA * ((v["tasmax"] + 273.16) ** 4 + (v["tasmin"] + 273.16) ** 4) / 2 - lw * et0.MJ_PER_W}
    u2, p = et0.wind_2m(v["sfcWind"]), et0.pressure(alt)
    e = {key: et0.reference(v["tasmax"], v["tasmin"], ea, es, u2, rns - r, p) for key, r in rnl.items()}
    water = soil.liquid(v["tas"], v["pr"], start)
    return {"days": days, "et0": e, "pr": v["pr"], "evap": evap, "alt": alt,
            "capacity": capacity,
            "bal": {key: soil.balance(water, x, capacity) for key, x in e.items()}}


def years(days):
    return days.astype("datetime64[Y]").astype(int) + 1970


def months(days):
    return days.astype("datetime64[M]").astype(int) % 12 + 1


def span(days, a, b):
    y = years(days)
    return (y >= a) & (y <= b)


def per_year(x, sel, n):
    """Somme annuelle moyenne sur n années."""
    return np.nansum(x[sel]) / n


def main():
    store, pts = Store(), np.load(DATA / "sol" / "points.npz")
    places = [str(p) for p in pts["places"]]
    cap = capacities(pts)
    res = {p: {s: compute(store, pts, k, s, cap[k]) for s in SPANS} for k, p in enumerate(places)}

    print(f"{LABEL} ({', '.join(f'{p} {c:.0f} mm' for p, c in zip(places, cap))}), p = {soil.DEPLETION_FRACTION}\n")
    print("1. ERA5 1991-2020, par an : pluie, ET0 (infrarouge FAO / flux), évapotranspiration réelle du bilan (FAO / flux), évaporation d'ERA5, mm")
    for p in places:
        r = res[p]["era5"]; s = span(r["days"], 1991, 2020)
        print(f"   {p:12s} alt {r['alt']:5.0f} m  pluie {per_year(r['pr'], s, 30):5.0f}  ET0 {per_year(r['et0']['fao'], s, 30):5.0f} / {per_year(r['et0']['flux'], s, 30):5.0f}"
              f"  ETR {per_year(r['bal']['fao'].eta, s, 30):5.0f} / {per_year(r['bal']['flux'].eta, s, 30):5.0f}  ERA5 {per_year(r['evap'], s, 30):5.0f}")

    print("\n2. Même tableau, MPI / ICON corrigé 1991-2020 (évaporation du modèle en dernière colonne)")
    for p in places:
        r = res[p]["cordex"]; s = span(r["days"], 1991, 2020)
        print(f"   {p:12s} pluie {per_year(r['pr'], s, 30):5.0f}  ET0 {per_year(r['et0']['fao'], s, 30):5.0f} / {per_year(r['et0']['flux'], s, 30):5.0f}"
              f"  ETR {per_year(r['bal']['fao'].eta, s, 30):5.0f} / {per_year(r['bal']['flux'].eta, s, 30):5.0f}  modèle {per_year(r['evap'], s, 30):5.0f}")

    def summer(r, key, a, b):
        s = span(r["days"], a, b) & np.isin(months(r["days"]), (6, 7, 8))
        bal = r["bal"][key]
        return np.nanmean(bal.fill[s]), (bal.ks[s] < 0.5).sum() / (b - a + 1), per_year(r["et0"][key], span(r["days"], a, b), b - a + 1)

    print("\n3. Été (juin à août), infrarouge FAO : remplissage moyen, jours par été avec Ks < 0,5, ET0 annuelle")
    print(f"   {'':12s} {'ERA5 1991-2020':>22s} {'modèle 1991-2020':>22s} {'modèle 2041-2070':>22s} {'modèle 2071-2100':>22s}")
    for p in places:
        cols = [summer(res[p]["era5"], "fao", 1991, 2020)] + [summer(res[p]["cordex"], "fao", a, b) for a, b in ((1991, 2020), (2041, 2070), (2071, 2100))]
        print(f"   {p:12s} " + " ".join(f"{100 * f:4.0f} % {d:4.0f} j {e:5.0f} mm" for f, d, e in cols))

    print("\n4. Étés notables à Paris et Grenoble, ERA5, infrarouge FAO : remplissage moyen de juin à août, rang parmi 1970-2025 (1 = le plus sec)")
    for p in ("Paris", "Grenoble"):
        r = res[p]["era5"]; jja = np.isin(months(r["days"]), (6, 7, 8)); y = years(r["days"])
        mean = {int(a): np.nanmean(r["bal"]["fao"].fill[jja & (y == a)]) for a in range(1970, 2026)}
        order = sorted(mean, key=mean.get)
        print(f"   {p:9s} " + ", ".join(f"{a} : {100 * mean[a]:.0f} % (rang {order.index(a) + 1})" for a in (1976, 2003, 2018, 2022))
              + f" ; les cinq plus secs : {order[:5]}")

    def season(r, a, b):
        """Par an : jours avec Ks < 0,5, déficit ET0 - ETR en mm, et jour moyen d'entrée et de sortie du stress (premier et dernier jour avec Ks < 0,5)."""
        bal = r["bal"]["fao"]; y = years(r["days"]); n = b - a + 1
        dry = bal.ks < 0.5
        doy = (r["days"] - r["days"].astype("datetime64[Y]")).astype(int) + 1
        first = [doy[dry & (y == k)].min() for k in range(a, b + 1) if (dry & (y == k)).any()]
        last = [doy[dry & (y == k)].max() for k in range(a, b + 1) if (dry & (y == k)).any()]
        s = span(r["days"], a, b)
        return dry[s].sum() / n, np.nansum((r["et0"]["fao"] - bal.eta)[s]) / n, np.mean(first) if first else np.nan, np.mean(last) if last else np.nan

    def day(d):
        return "  --  " if d != d else (np.datetime64("2001-01-01") + int(round(d)) - 1).astype(object).strftime("%d/%m")

    print("\n5. Année entière, infrarouge FAO : jours par an avec Ks < 0,5, déficit ET0 - ETR par an, premier et dernier jour de stress (moyennes)")
    print(f"   {'':12s} {'ERA5 1991-2020':>30s} {'modèle 1991-2020':>30s} {'modèle 2041-2070':>30s} {'modèle 2071-2100':>30s}")
    for p in places:
        cols = [season(res[p]["era5"], 1991, 2020)] + [season(res[p]["cordex"], a, b) for a, b in ((1991, 2020), (2041, 2070), (2071, 2100))]
        print(f"   {p:12s} " + " ".join(f"{d:4.0f} j {x:4.0f} mm {day(f)}-{day(l)}" for d, x, f, l in cols))

    # Figure 1 : cycle annuel moyen du remplissage.
    fig, axes = plt.subplots(1, len(places), figsize=(4 * len(places), 3.6), sharey=True)
    curves = (("era5", 1991, 2020, "black", "ERA5 1991-2020"), ("cordex", 1991, 2020, "tab:blue", "modèle 1991-2020"),
              ("cordex", 2041, 2070, "tab:orange", "modèle 2041-2070"), ("cordex", 2071, 2100, "tab:red", "modèle 2071-2100"))
    for ax, p in zip(axes, places):
        for source, a, b, color, label in curves:
            r = res[p][source]; s = span(r["days"], a, b); m = months(r["days"])
            ax.plot(range(1, 13), [100 * np.nanmean(r["bal"]["fao"].fill[s & (m == k)]) for k in range(1, 13)], color=color, label=label)
        ax.set_title(p); ax.set_xticks(range(1, 13)); ax.set_xticklabels("JFMAMJJASOND"); ax.set_ylim(0, 100); ax.grid(alpha=0.3)
    axes[0].set_ylabel("remplissage du réservoir (%)"); axes[0].legend(fontsize=8)
    fig.suptitle(f"Remplissage moyen par mois, {LABEL}, gazon de référence")
    fig.tight_layout(); fig.savefig(OUT / f"cycle_{TAG}.png", dpi=130); plt.close(fig)

    # Figure 2 : remplissage moyen de l'été, année par année.
    fig, axes = plt.subplots(len(places), 1, figsize=(11, 2.2 * len(places)), sharex=True)
    for ax, p in zip(axes, places):
        for source, color, a, b in (("era5", "black", 1970, 2025), ("cordex", "tab:red", 1970, 2100)):
            r = res[p][source]; jja = np.isin(months(r["days"]), (6, 7, 8)); y = years(r["days"])
            ax.plot(range(a, b + 1), [100 * np.nanmean(r["bal"]["fao"].fill[jja & (y == k)]) for k in range(a, b + 1)],
                    color=color, lw=1, label="ERA5" if source == "era5" else "MPI / ICON corrigé")
        ax.set_ylim(0, 100); ax.set_ylabel(p); ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, ncol=2); axes[0].set_title(f"Remplissage moyen de juin à août (%), {LABEL}")
    fig.tight_layout(); fig.savefig(OUT / f"etes_{TAG}.png", dpi=130); plt.close(fig)

    # Figure 3 : 2003 et 2022 jour par jour à Paris, contre la plage 1991-2020.
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6), sharey=True)
    r = res["Paris"]["era5"]; y = years(r["days"]); fill = 100 * r["bal"]["fao"].fill
    doy = (r["days"] - r["days"].astype("datetime64[Y]")).astype(int)
    ref = np.array([[np.nanpercentile(fill[span(r["days"], 1991, 2020) & (doy == d)], q) for d in range(365)] for q in (10, 50, 90)])
    for ax, year in zip(axes, (2003, 2022)):
        ax.fill_between(range(365), ref[0], ref[2], color="0.85", label="1991-2020, 10e au 90e centile")
        ax.plot(range(365), ref[1], color="0.5", lw=1, label="médiane")
        ax.plot(doy[y == year][:365], fill[y == year][:365], color="tab:red", label=str(year))
        ax.set_title(f"Paris, {year}"); ax.set_xlabel("jour de l'année"); ax.set_ylim(0, 100); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    axes[0].set_ylabel("remplissage du réservoir (%)")
    fig.tight_layout(); fig.savefig(OUT / f"paris_2003_2022_{TAG}.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    main()
