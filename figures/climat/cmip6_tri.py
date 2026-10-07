"""Tri des simulations EURO-CORDEX-CMIP6 (EUR-12) en moyennes mensuelles, sur la France métropolitaine.

    python3 figures/climat/cmip6_tri.py telecharger
    ~/Projets_data/VirtualEnv/weather_simulator_v2/bin/python figures/climat/cmip6_tri.py analyser

telecharger : tas et tasmax mensuels, historical puis ssp370 (ou evaluation pour les simulations pilotées
par ERA5), et le masque sftlf, de chaque simulation de RUNS, depuis ESGF (catalogue STAC, SHA256 et
reprise de src.download.cordex6). Fichiers dans data/cordex/mensuel/<modèle global>_<régional>_<institut>/.

analyser : mailles dont le centre est en France métropolitaine et terrestres (sftlf ≥ 50 %), moyenne
simple ; année et été (JJA) pondérés par le nombre de jours des mois ; écarts à 1976-2005 ; niveaux de
la TRACC comme cmip6_futur.py. ERA5-Land et RCA4 : figures/climat/cmip6_futur.csv.
Écrit figures/climat/cmip6_tri.csv (séries annuelles) et affiche les tableaux.
"""
import sys
from pathlib import Path as P

ROOT = P(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "cordex" / "mensuel"
VARS = ["tas", "tasmax"]
# (modèle global, membre, modèle régional, institut, expériences)
RUNS = [
    ("CNRM-ESM2-1", "r1i1p1f2", "ICON-CLM-202407-1-1", "CLMcom-BTU", ["historical", "ssp370"]),
    ("MPI-ESM1-2-HR", "r1i1p1f1", "ICON-CLM-202407-1-1", "CLMcom-DWD", ["historical", "ssp370"]),
    ("MIROC6", "r1i1p1f1", "ICON-CLM-202407-1-1", "CLMcom-KIT", ["historical", "ssp370"]),
    ("MIROC6", "r1i1p1f1", "CCLM6-0-1", "CLMcom-KIT", ["historical", "ssp370"]),
    ("EC-Earth3-Veg", "r1i1p1f1", "CCLM6-0-1", "CLMcom-KIT", ["historical", "ssp370"]),
    ("CMCC-CM2-SR5", "r1i1p1f1", "CNRM-ALADIN64E1", "CNRM-MF", ["historical", "ssp370"]),
    ("NorESM2-MM", "r1i1p1f1", "CNRM-ALADIN64E1", "CNRM-MF", ["historical", "ssp370"]),
    ("ERA5", "r1i1p1f1", "ICON-CLM-202407-1-1", "CLMcom-Hereon", ["evaluation"]),
    ("ERA5", "r1i1p1f1", "CNRM-ALADIN64E1", "CNRM-MF", ["evaluation"]),
]


def nom(run):
    return f"{run[0]}_{run[2]}_{run[3]}"


def telecharger():
    import time

    import src.download.cordex6 as c

    todo = []
    for run in RUNS:
        gcm, member, rcm, inst, exps = run
        c.RUN = {"domain_id": "EUR-12", "institution_id": inst, "driving_source_id": gcm,
                 "driving_variant_label": member, "source_id": rcm,
                 # v1-r2 of the ERA5-driven ICON run uses a shorter time step: v1-r1 matches the scenarios.
                 "version_realization": "v1-r1"}
        dest = OUT / nom(run)
        dest.mkdir(parents=True, exist_ok=True)
        for var in VARS:
            for exp in exps:
                items = c.query(exp, "mon", var)
                if len(items) != 1:
                    raise SystemExit(f"{nom(run)} {var} {exp}: {len(items)} jeux de données")
                # Nothing before 1976 is used: the reference is 1976-2005.
                todo += [(dest, f) for f in c.files_of(items[0]) if c.span(f["name"])[1] >= 1976]
        items = c.query(exps[0], "fx", "sftlf")
        todo += [(dest, f) for f in c.files_of(items[0])]
    todo = [(d, f) for d, f in todo if not (d / f["name"]).exists()]
    print(f"{len(todo)} fichiers, {sum(f['size'] for _, f in todo) / 1e9:.2f} Go", flush=True)
    failed = []
    for n, (dest, f) in enumerate(todo, 1):
        c.OUT = dest
        for attempt in range(1, c.TRIES + 1):
            try:
                c.fetch(f)
                print(f"  [{n}/{len(todo)}] {f['name']}  {f['size'] / 1e6:4.0f} Mo  SHA256 ok", flush=True)
                break
            except Exception as err:
                print(f"  [{n}/{len(todo)}] {f['name']} essai {attempt} echoue : {type(err).__name__}", flush=True)
                if attempt == c.TRIES:
                    failed.append(f["name"])
                else:
                    time.sleep(10)
    if failed:
        print(f"{len(failed)} echecs, relancer : {failed}")


def analyser():
    import warnings

    import numpy as np
    import pandas as pd
    import xarray as xr

    sys.path.insert(0, str(ROOT / "figures" / "climat"))
    from cmip6_test import masque_france
    from cmip6_futur import NIVEAUX, niveau

    warnings.filterwarnings("ignore")

    def serie(dest, var):
        ds = xr.open_mfdataset(sorted(dest.glob(f"{var}_*_mon_*.nc")), combine="by_coords")
        terre = xr.open_dataset(next(dest.glob("sftlf_*.nc"))).sftlf.values >= 50
        m = masque_france(ds.lat.values, ds.lon.values, terre)
        y, x = ds[var].dims[-2:]
        da = ds[var].where(xr.DataArray(m, dims=(y, x))).mean((y, x)).load() - 273.15
        s = da.to_series()
        # Calendars differ between runs (numpy dates or cftime): only year and month are kept.
        t = da.time.to_index()
        s.index = pd.to_datetime(pd.DataFrame({"year": t.year, "month": t.month, "day": 1}))
        jours = s.index.days_in_month
        an = (s * jours).groupby(s.index.year).sum() / pd.Series(jours, s.index).groupby(s.index.year).sum()
        e = s.index.month.isin([6, 7, 8])
        jja = (s[e] * jours[e]).groupby(s.index.year[e]).sum() / pd.Series(jours[e], s.index[e]).groupby(s.index.year[e]).sum()
        complet = pd.Series(1, s.index).groupby(s.index.year).sum() == 12
        return an[complet[complet].index.intersection(an.index)], jja, int(m.sum())

    cols = {}
    for run in RUNS:
        dest = OUT / nom(run)
        an, jja, n = serie(dest, "tas")
        _, txj, _ = serie(dest, "tasmax")
        k = f"{run[0]} / {run[2].split('-202')[0]}"
        cols[(k, "tas_AN")], cols[(k, "tas_JJA")], cols[(k, "Tx_JJA")] = an, jja, txj
        print(f"{k}: {n} mailles, {an.index.min()}-{an.index.max()}", flush=True)
    df = pd.DataFrame(cols)
    ref = pd.read_csv(ROOT / "figures/climat/cmip6_futur.csv", header=[0, 1], index_col=0)
    ref.index = ref.index.astype(int)
    anom = df - df.loc[1976:2005].mean()
    for src, k in [("era5land", "ERA5-Land"), ("rca4", "EC-EARTH / RCA4 (RCP4.5)")]:
        for ind in ["tas_AN", "tas_JJA", "Tx_JJA"]:
            anom[(k, ind)] = ref[(src, ind)]
    anom.columns = pd.MultiIndex.from_tuples(anom.columns, names=["simulation", "indicateur"])
    anom.to_csv(ROOT / "figures/climat/cmip6_tri.csv", float_format="%.3f")

    pente = lambda s: 10 * np.polyfit(s.index, s.values, 1)[0]
    lignes = []
    for k in anom.columns.get_level_values(0).unique():
        a = anom[(k, "tas_AN")].dropna()
        tx = anom[(k, "Tx_JJA")].dropna()
        r = a.rolling(20, center=True).mean()
        lignes.append({
            "simulation": k,
            "tend 2006-25": pente(a.loc[2006:2025]) if a.index.max() >= 2025 else np.nan,
            "AN 96-25": a.loc[1996:2025].mean() if a.index.max() >= 2025 else np.nan,
            "AN 16-25": a.loc[2016:2025].mean() if a.index.max() >= 2025 else np.nan,
            "AN 41-60": a.loc[2041:2060].mean() if a.index.max() >= 2060 else np.nan,
            "AN 81-00": a.loc[2081:2100].mean() if a.index.max() >= 2099 else np.nan,
            "Tx 96-25": tx.loc[1996:2025].mean() if tx.index.max() >= 2025 else np.nan,
            "Tx 41-60": tx.loc[2041:2060].mean() if tx.index.max() >= 2060 else np.nan,
            "Tx 81-00": tx.loc[2081:2100].mean() if tx.index.max() >= 2099 else np.nan,
            **{f"+{n} K": niveau(a, n) for n in NIVEAUX},
            "max 20 ans": r.max(),
        })
    t = pd.DataFrame(lignes).set_index("simulation")
    pd.set_option("display.width", 250)
    print("\nÉcarts à 1976-2005, France (K). AN : température annuelle ; Tx : Tx d'été. "
          "Niveaux : année centrale de la moyenne glissante 20 ans (TRACC : 2030, 2050, 2100).")
    print(t.round(2).to_string())


def tracer():
    """Un panneau par simulation, même échelle : tas annuelle et Tx d'été, écarts à 1976-2005."""
    import matplotlib.pyplot as plt
    import pandas as pd

    a = pd.read_csv(ROOT / "figures/climat/cmip6_tri.csv", header=[0, 1], index_col=0)
    a.index = a.index.astype(int)
    sims = [k for k in a.columns.get_level_values(0).unique()
            if k not in ("ERA5-Land", "EC-EARTH / RCA4 (RCP4.5)")]
    INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e4e0"
    MOD, OBS, RCA = "#1baf7a", "#2a78d6", "#eb6834"
    TRACC = [(2030, 1.4), (2050, 2.1), (2100, 3.4)]

    def fin(r):
        """Ancrage de l'étiquette de fin : au-delà du losange TRACC de 2100 pour les séries longues."""
        return (2102.5 if r.index[-1] > 2080 else r.index[-1] + 1.5, r.iloc[-1])

    for ind, titre, fichier in [("tas_AN", "Température moyenne annuelle", "cmip6_tri_tas.png"),
                                ("Tx_JJA", "Température maximale moyenne de l'été (juin-août)", "cmip6_tri_tx.png")]:
        fig, axes = plt.subplots(3, 3, figsize=(15, 11), sharex=True, sharey=True)
        for ax, k in zip(axes.flat, sims):
            for src, c, ls, lw, lab in [("EC-EARTH / RCA4 (RCP4.5)", RCA, ":", 1.8, "RCA4, RCP4.5 (modèle actuel)"),
                                        ("ERA5-Land", OBS, "-", 2.2, "ERA5-Land (observé)"),
                                        (k, MOD, "-", 2.4, "simulation du panneau")]:
                s = a[(src, ind)].dropna()
                if src == k:
                    ax.plot(s.index, s, color=c, lw=0.9, alpha=0.35)
                r = s.rolling(20, center=True).mean().dropna()
                ax.plot(r.index, r, color=c, ls=ls, lw=lw, label=lab)
                if src == k and len(r):
                    ax.annotate(f"{r.iloc[-1]:+.1f}".replace(".", ","), fin(r),
                                xytext=(0, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
            # Valeur finale de RCA4, décalée sous celle de la simulation quand les deux se touchent.
            r = a[("EC-EARTH / RCA4 (RCP4.5)", ind)].dropna().rolling(20, center=True).mean().dropna()
            m = a[(k, ind)].dropna().rolling(20, center=True).mean().dropna()
            dy = -9 if len(m) and abs(m.index[-1] - r.index[-1]) < 5 and abs(m.iloc[-1] - r.iloc[-1]) < 0.7 else 0
            if dy and r.iloc[-1] > m.iloc[-1]:
                dy = 9
            ax.annotate(f"{r.iloc[-1]:+.1f}".replace(".", ","), fin(r), xytext=(0, dy),
                        textcoords="offset points", va="center", fontsize=9, color=MUTED)
            if ind == "tas_AN":
                for y, v in TRACC:
                    ax.plot(y, v, "D", ms=6, color=INK, mec="white", mew=1.5, zorder=5,
                            label="niveaux TRACC" if y == 2030 else None)
            ax.set_title(k, loc="left", fontsize=10.5, color=INK)
            ax.axhline(0, color=MUTED, lw=0.7)
            ax.grid(axis="y", color=GRID, lw=0.8)
            ax.spines[["top", "right"]].set_visible(False)
            ax.spines[["left", "bottom"]].set_color(MUTED)
            ax.tick_params(colors=MUTED, labelsize=9)
        for ax in axes[:, 0]:
            ax.set_ylabel("Écart à 1976-2005 (K)", color=MUTED)
        for ax in axes.flat[len(sims):]:
            ax.set_visible(False)
        axes[0, 0].set_xlim(1974, 2112)
        h, l = axes[0, 0].get_legend_handles_labels()
        fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.005, 0.962), ncol=4, frameon=False, fontsize=9.5)
        fig.suptitle(f"{titre}, France métropolitaine : simulations EURO-CORDEX-CMIP6 (SSP3-7.0)",
                     x=0.01, ha="left", fontsize=13, color=INK)
        fig.text(0.01, 0.005, "Moyennes glissantes sur 20 ans (centrées) ; trait fin : simulation année par année. "
                 "Modèles bruts, moyennes mensuelles ; écarts pris dans chaque source. Chiffre gris : RCA4. "
                 "ERA5 / ... : simulations pilotées par la réanalyse ERA5 (évaluation, jusqu'en 2024).",
                 fontsize=8, color=MUTED)
        fig.tight_layout(rect=(0, 0.02, 1, 0.93))
        fig.savefig(ROOT / "figures/climat" / fichier, dpi=130)
        print("écrit", fichier)


if __name__ == "__main__":
    {"telecharger": telecharger, "analyser": analyser, "tracer": tracer}[sys.argv[1]]()
