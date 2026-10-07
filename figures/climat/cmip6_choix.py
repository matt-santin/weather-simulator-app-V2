"""Figure du choix du modèle CORDEX-CMIP6 (docs/choix_modele_cmip6.md), à partir de figures/climat/cmip6_tri.csv.

Deux simulations EUR-12 SSP3-7.0 (CNRM-ESM2-1 / ICON-CLM et MPI-ESM1-2-HR / ICON-CLM) face à RCA4 (RCP4.5)
et ERA5-Land, France métropolitaine, écarts à 1976-2005 : température annuelle en haut, Tx d'été en bas.
    ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/cmip6_choix.py
"""
from pathlib import Path as P

import matplotlib.pyplot as plt
import pandas as pd

D = P(__file__).resolve().parent
SIMS = ["CNRM-ESM2-1 / ICON-CLM", "MPI-ESM1-2-HR / ICON-CLM"]
RCA4, OBS = "EC-EARTH / RCA4 (RCP4.5)", "ERA5-Land"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e4e0"
MOD, BLEU, ORANGE = "#1baf7a", "#2a78d6", "#eb6834"
TRACC = [(2030, 1.4), (2050, 2.1), (2100, 3.4)]

a = pd.read_csv(D / "cmip6_tri.csv", header=[0, 1], index_col=0)
a.index = a.index.astype(int)


def fin(r):
    """Ancrage de l'étiquette de fin : au-delà du losange TRACC de 2100 pour les séries longues."""
    return (2102.5 if r.index[-1] > 2080 else r.index[-1] + 1.5, r.iloc[-1])


fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True, sharey="row")
for i, (ind, titre) in enumerate([("tas_AN", "Température moyenne annuelle"),
                                  ("Tx_JJA", "Température maximale moyenne de l'été (juin-août)")]):
    for j, k in enumerate(SIMS):
        ax = axes[i, j]
        for src, c, ls, lw, lab in [(RCA4, ORANGE, ":", 1.8, "RCA4, RCP4.5 (modèle actuel)"),
                                    (OBS, BLEU, "-", 2.2, "ERA5-Land (observé)"),
                                    (k, MOD, "-", 2.4, "simulation du panneau, SSP3-7.0")]:
            s = a[(src, ind)].dropna()
            if src == k:
                ax.plot(s.index, s, color=c, lw=0.9, alpha=0.35)
            r = s.rolling(20, center=True).mean().dropna()
            ax.plot(r.index, r, color=c, ls=ls, lw=lw, label=lab)
        r = a[(k, ind)].dropna().rolling(20, center=True).mean().dropna()
        q = a[(RCA4, ind)].dropna().rolling(20, center=True).mean().dropna()
        haut = 9 if r.iloc[-1] >= q.iloc[-1] else -9
        ax.annotate(f"{r.iloc[-1]:+.1f}".replace(".", ","), fin(r), xytext=(0, haut if abs(r.iloc[-1] - q.iloc[-1]) < 0.7 else 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
        ax.annotate(f"{q.iloc[-1]:+.1f}".replace(".", ","), fin(q), xytext=(0, -haut if abs(r.iloc[-1] - q.iloc[-1]) < 0.7 else 0),
                    textcoords="offset points", va="center", fontsize=9, color=MUTED)
        if ind == "tas_AN":
            for y, v in TRACC:
                ax.plot(y, v, "D", ms=6, color=INK, mec="white", mew=1.5, zorder=5,
                        label="niveaux TRACC" if y == 2030 else None)
        ax.set_title(f"{k} : {titre.lower()}", loc="left", fontsize=10.5, color=INK)
        ax.axhline(0, color=MUTED, lw=0.7)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9)
    axes[i, 0].set_ylabel("Écart à 1976-2005 (K)", color=MUTED)
axes[0, 0].set_xlim(1974, 2112)
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.005, 0.955), ncol=4, frameon=False, fontsize=9.5)
fig.suptitle("France métropolitaine : CNRM-ESM2-1 / ICON-CLM et MPI-ESM1-2-HR / ICON-CLM face à RCA4",
             x=0.01, ha="left", fontsize=13, color=INK)
fig.text(0.01, 0.005, "Moyennes glissantes sur 20 ans (centrées) ; trait fin : simulation année par année. "
         "Modèles bruts, moyennes mensuelles ; écarts pris dans chaque source. Chiffre noir : simulation ; gris : RCA4.",
         fontsize=8, color=MUTED)
fig.tight_layout(rect=(0, 0.02, 1, 0.92))
fig.savefig(D / "cmip6_choix.png", dpi=130)
print("écrit", D / "cmip6_choix.png")
