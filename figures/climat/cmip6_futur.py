"""Futur du candidat CORDEX-CMIP6 : ICON (SSP3-7.0) face à RCA4 (RCP4.5), France métropolitaine.

Mêmes définitions que docs/resultats_rcp45.md : moyennes France, écarts à 1976-2005, niveaux de la
TRACC (+1,4, +2,1, +3,4 K) atteints quand la moyenne glissante sur 20 ans (centrée, année affichée =
année centrale, convention pandas) de la température annuelle les dépasse.

Sources : ICON brut (1976-2100), RCA4 brut (1976-2100, lu sur le LaCie), RCA4 corrigé (cordex010,
figures/climat/france_agregats.csv), ERA5-Land (1976-2025). Les écarts à 1976-2005 sont pris dans
chaque source : le biais moyen s'annule, seul le réchauffement compte.

Écrit figures/climat/cmip6_futur.csv (séries annuelles) et affiche les tableaux.
    ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/cmip6_futur.py
"""
import sys
import warnings
from pathlib import Path as P

import numpy as np
import pandas as pd

sys.path.insert(0, str(P(__file__).resolve().parent))
import cmip6_test as T  # noqa: E402

warnings.filterwarnings("ignore")
T.Y0, T.Y1 = 1976, 2100
REF = (1976, 2005)
NIVEAUX = [1.4, 2.1, 3.4]
PERIODES = [(2016, 2025), (2041, 2060), (2071, 2100), (2081, 2100)]
OUT = P("figures/climat/cmip6_futur.csv")


def annuel(s):
    """Moyenne annuelle et moyenne estivale (JJA) d'une série journalière."""
    s.index = pd.to_datetime(s.index).normalize()
    ete = s[s.index.month.isin([6, 7, 8])]
    return s.groupby(s.index.year).mean(), ete.groupby(ete.index.year).mean()


def niveau(anom, seuil):
    r = anom.rolling(20, center=True).mean()
    ok = r[r >= seuil]
    return int(ok.index[0]) if len(ok) else None


if __name__ == "__main__":
    series = {}
    for src, f in [("era5land", T.era5land), ("icon", lambda v: T.modele("icon", v)),
                   ("rca4", lambda v: T.modele("rca4", v))]:
        for var in ["tas", "tasmax"]:
            fr, _, n = f(var)
            an, ete = annuel(fr)
            if var == "tas":
                series[(src, "tas_AN")], series[(src, "tas_JJA")] = an, ete
            else:
                series[(src, "Tx_JJA")] = ete
            print(f"{src} {var}: {n} mailles, {an.index.min()}-{an.index.max()}", flush=True)

    ag = pd.read_csv("figures/climat/france_agregats.csv")
    ag = ag[(ag.source == "cordex010") & (ag.variable.isin(["tas", "tasmax"]))]
    for var, sai, nom in [("tas", "AN", "tas_AN"), ("tas", "JJA", "tas_JJA"), ("tasmax", "JJA", "Tx_JJA")]:
        x = ag[(ag.variable == var) & (ag.saison == sai)].set_index("annee").valeur
        series[("rca4_corrige", nom)] = x[(x.index >= T.Y0) & (x.index <= T.Y1)]

    df = pd.DataFrame(series)
    df.columns.names = ["source", "indicateur"]
    anom = df - df.loc[REF[0]:REF[1]].mean()
    anom.to_csv(OUT, float_format="%.3f")

    pd.set_option("display.width", 200)
    sources = ["era5land", "icon", "rca4", "rca4_corrige"]
    for ind in ["tas_AN", "tas_JJA", "Tx_JJA"]:
        t = pd.DataFrame({f"{a}-{b}": anom.loc[a:b, [(s, ind) for s in sources]].mean().droplevel(1)
                          for a, b in PERIODES}).T
        print(f"\n== {ind}, écart à {REF[0]}-{REF[1]} (K)")
        print(t.round(2).to_string())

    print("\n== Niveaux TRACC (température annuelle, moyenne glissante 20 ans, année centrale)")
    print("TRACC : +1,4 K en 2030, +2,1 K en 2050, +3,4 K en 2100")
    for s in sources:
        a = anom[(s, "tas_AN")].dropna()
        print(f"  {s:13}", "  ".join(f"+{n} K : {niveau(a, n) or 'jamais'}" for n in NIVEAUX),
              f"  (max {a.rolling(20, center=True).mean().max():+.2f} K)")

    # Calage sur une autre période : en moyenne, la correction additive ramène la période de calage
    # sur ERA5-Land et ajoute le changement du modèle depuis cette période. Retard en 2016-2025 =
    # (ERA5-Land 2016-2025 - ERA5-Land calage) - (modèle 2016-2025 - modèle calage).
    print("\n== Retard sur ERA5-Land en 2016-2025 après correction, selon la période de calage (K)")
    for cal in [(1976, 2005), (1996, 2025)]:
        for ind in ["tas_AN", "tas_JJA", "Tx_JJA"]:
            obs = anom[("era5land", ind)]
            d_obs = obs.loc[2016:2025].mean() - obs.loc[cal[0]:cal[1]].mean()
            ret = {s: anom[(s, ind)].loc[2016:2025].mean() - anom[(s, ind)].loc[cal[0]:cal[1]].mean() - d_obs
                   for s in ["icon", "rca4"]}
            print(f"  calage {cal[0]}-{cal[1]}  {ind:8}", "  ".join(f"{s} {v:+.2f}" for s, v in ret.items()))
    print("écrit", OUT)
