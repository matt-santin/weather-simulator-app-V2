"""Réchauffement 1976-2005 → 1996-2025 : ICON (CORDEX-CMIP6), RCA4 et ERA5-Land, bruts.

Même lecture que cmip6_test.py (France métropolitaine, villes), sur 1976-2025. Pour chaque source,
écart entre les moyennes 1996-2025 et 1976-2005 : Tx en été (moyenne, P90, P99, jours ≥ 30 °C par été)
et tas annuelle. C'est le test fait sur RCA4 corrigé le 2 octobre 2026 (Tx JJA : ERA5-Land
+1,0 à +1,5 K, CORDEX corrigé +0,4 à +0,8 K).

Écrit figures/climat/cmip6_periodes.csv et affiche le tableau.
    ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/cmip6_periodes.py
"""
import sys
import warnings
from pathlib import Path as P

import pandas as pd

sys.path.insert(0, str(P(__file__).resolve().parent))
import cmip6_test as T  # noqa: E402

warnings.filterwarnings("ignore")
T.Y0, T.Y1 = 1976, 2025
AVANT, APRES = (1976, 2005), (1996, 2025)
OUT = P("figures/climat/cmip6_periodes.csv")


def ecarts(s, var):
    s.index = pd.to_datetime(s.index).normalize()
    a = s[(s.index.year >= AVANT[0]) & (s.index.year <= AVANT[1])]
    b = s[(s.index.year >= APRES[0]) & (s.index.year <= APRES[1])]
    if var == "tas":
        return {"dtas_AN": b.mean() - a.mean()}
    ja, jb = a[a.index.month.isin([6, 7, 8])], b[b.index.month.isin([6, 7, 8])]
    j30 = lambda x: (x >= 30).sum() / x.index.year.nunique()
    return {"dTx_JJA": jb.mean() - ja.mean(), "dP90": jb.quantile(0.9) - ja.quantile(0.9),
            "dP99": jb.quantile(0.99) - ja.quantile(0.99), "j30_avant": j30(ja), "j30_apres": j30(jb)}


if __name__ == "__main__":
    lignes = {}
    for var in ["tasmax", "tas"]:
        for src, f in [("era5land", T.era5land), ("icon", lambda v: T.modele("icon", v)),
                       ("rca4", lambda v: T.modele("rca4", v))]:
            fr, villes, n = f(var)
            print(f"{var} {src}: {n} mailles France, {len(fr)} jours", flush=True)
            for lieu, s in [("France", fr), *villes.items()]:
                lignes.setdefault((src, lieu), {}).update(ecarts(s, var))
    df = pd.DataFrame([{"source": k[0], "lieu": k[1], **v} for k, v in lignes.items()])
    df.to_csv(OUT, index=False, float_format="%.3f")
    pd.set_option("display.width", 200)
    for col in ["dTx_JJA", "dP90", "dP99", "j30_avant", "j30_apres", "dtas_AN"]:
        print(f"\n== {col}")
        print(df.pivot(index="lieu", columns="source", values=col).round(2).to_string())
    print("écrit", OUT)
